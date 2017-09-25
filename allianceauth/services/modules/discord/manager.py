import requests
import json
import re
from django.conf import settings
from requests_oauthlib import OAuth2Session
from functools import wraps
import logging
import datetime
import time
from django.core.cache import cache
from hashlib import md5

logger = logging.getLogger(__name__)

DISCORD_URL = "https://discordapp.com/api"
EVE_IMAGE_SERVER = "https://image.eveonline.com"

AUTH_URL = "https://discordapp.com/api/oauth2/authorize"
TOKEN_URL = "https://discordapp.com/api/oauth2/token"

"""
Previously all we asked for was permission to kick members, manage roles, and manage nicknames.
Users have reported weird unauthorized errors we don't understand. So now we ask for full server admin.
It's almost fixed the problem.
"""
# kick members, manage roles, manage nicknames
# BOT_PERMISSIONS = 0x00000002 + 0x10000000 + 0x08000000
BOT_PERMISSIONS = 0x00000008

# get user ID, accept invite
SCOPES = [
    'identify',
    'guilds.join',
]

GROUP_CACHE_MAX_AGE = int(getattr(settings, 'DISCORD_GROUP_CACHE_MAX_AGE', 2 * 60 * 60))  # 2 hours default


class DiscordApiException(Exception):
    def __init__(self):
        super(Exception, self).__init__()


class DiscordApiTooBusy(DiscordApiException):
    def __init__(self):
        super(DiscordApiException, self).__init__()
        self.message = "The Discord API is too busy to process this request now, please try again later."


class DiscordApiBackoff(DiscordApiException):
    def __init__(self, retry_after, global_ratelimit):
        super(DiscordApiException, self).__init__()
        self.retry_after = retry_after
        self.global_ratelimit = global_ratelimit


cache_time_format = '%Y-%m-%d %H:%M:%S'


def api_backoff(func):
    """
    Decorator, Handles HTTP 429 "Too Many Requests" messages from the Discord API
    If blocking=True is specified, this function will block and retry
    the function up to max_retries=n times, or 3 if retries is not specified.
    If the API call still recieves a backoff timer this function will raise
    a <DiscordApiTooBusy> exception.
    If the caller chooses blocking=False, the decorator will raise a DiscordApiBackoff
    exception and the caller can choose to retry after the given timespan available in
    the retry_after property in seconds.
    """

    class PerformBackoff(Exception):
        def __init__(self, retry_after, retry_datetime, global_ratelimit):
            super(Exception, self).__init__()
            self.retry_after = int(retry_after)
            self.retry_datetime = retry_datetime
            self.global_ratelimit = global_ratelimit

    @wraps(func)
    def decorated(*args, **kwargs):
        blocking = kwargs.get('blocking', False)
        retries = kwargs.get('max_retries', 3)

        # Strip our parameters
        if 'max_retries' in kwargs:
            del kwargs['max_retries']
        if 'blocking' in kwargs:
            del kwargs['blocking']

        cache_key = 'DISCORD_BACKOFF_' + func.__name__
        cache_global_key = 'DISCORD_BACKOFF_GLOBAL'

        while retries > 0:
            try:
                try:
                    # Check global backoff first, then route backoff
                    existing_global_backoff = cache.get(cache_global_key)
                    existing_backoff = existing_global_backoff or cache.get(cache_key)
                    if existing_backoff:
                        backoff_timer = datetime.datetime.strptime(existing_backoff, cache_time_format)
                        if backoff_timer > datetime.datetime.utcnow():
                            backoff_seconds = (backoff_timer - datetime.datetime.utcnow()).total_seconds()
                            logger.debug("Still under backoff for {} seconds, backing off" % backoff_seconds)
                            # Still under backoff
                            raise PerformBackoff(
                                retry_after=backoff_seconds,
                                retry_datetime=backoff_timer,
                                global_ratelimit=bool(existing_global_backoff)
                            )
                    logger.debug("Calling API calling function")
                    func(*args, **kwargs)
                    break
                except requests.HTTPError as e:
                    if e.response.status_code == 429:
                        try:
                            retry_after = int(e.response.headers['Retry-After'])
                        except (TypeError, KeyError):
                            # Pick some random time
                            retry_after = 5000

                        logger.info("Received backoff from API of %s seconds, handling" % retry_after)
                        # Store value in redis
                        backoff_until = (datetime.datetime.utcnow() +
                                         datetime.timedelta(milliseconds=retry_after))
                        global_backoff = bool(e.response.headers.get('X-RateLimit-Global', False))
                        if global_backoff:
                            logger.info("Global backoff!!")
                            cache.set(cache_global_key, backoff_until.strftime(cache_time_format), retry_after)
                        else:
                            cache.set(cache_key, backoff_until.strftime(cache_time_format), retry_after)
                        raise PerformBackoff(retry_after=retry_after, retry_datetime=backoff_until,
                                             global_ratelimit=global_backoff)
                    else:
                        # Not 429, re-raise
                        raise e
            except PerformBackoff as bo:
                # Sleep if we're blocking
                if blocking:
                    logger.info("Blocking Back off from API calls for %s seconds" % bo.retry_after)
                    time.sleep(10 if bo.retry_after > 10 else bo.retry_after)
                else:
                    # Otherwise raise exception and let caller handle the backoff
                    raise DiscordApiBackoff(retry_after=bo.retry_after, global_ratelimit=bo.global_ratelimit)
            finally:
                retries -= 1
        if retries == 0:
            raise DiscordApiTooBusy()
    return decorated


class DiscordOAuthManager:
    def __init__(self):
        pass

    @staticmethod
    def _sanitize_name(name):
        return re.sub('[^\w.-]', '', name)[:32]

    @staticmethod
    def _sanitize_groupname(name):
        name = name.strip(' _')
        return DiscordOAuthManager._sanitize_name(name)

    @staticmethod
    def generate_bot_add_url():
        return AUTH_URL + '?client_id=' + settings.DISCORD_APP_ID + '&scope=bot&permissions=' + str(BOT_PERMISSIONS)

    @staticmethod
    def generate_oauth_redirect_url():
        oauth = OAuth2Session(settings.DISCORD_APP_ID, redirect_uri=settings.DISCORD_CALLBACK_URL, scope=SCOPES)
        url, state = oauth.authorization_url(AUTH_URL)
        return url

    @staticmethod
    def _process_callback_code(code):
        oauth = OAuth2Session(settings.DISCORD_APP_ID, redirect_uri=settings.DISCORD_CALLBACK_URL)
        token = oauth.fetch_token(TOKEN_URL, client_secret=settings.DISCORD_APP_SECRET, code=code)
        return token

    @staticmethod
    def add_user(code):
        try:
            token = DiscordOAuthManager._process_callback_code(code)['access_token']
            logger.debug("Received token from OAuth")

            custom_headers = {'accept': 'application/json', 'authorization': 'Bearer ' + token}
            path = DISCORD_URL + "/invites/" + str(settings.DISCORD_INVITE_CODE)
            r = requests.post(path, headers=custom_headers)
            logger.debug("Got status code %s after accepting Discord invite" % r.status_code)
            r.raise_for_status()

            path = DISCORD_URL + "/users/@me"
            r = requests.get(path, headers=custom_headers)
            logger.debug("Got status code %s after retrieving Discord profile" % r.status_code)
            r.raise_for_status()

            user_id = r.json()['id']
            logger.info("Added Discord user ID %s to server." % user_id)
            return user_id
        except:
            logger.exception("Failed to add Discord user")
            return None

    @staticmethod
    def update_nickname(user_id, nickname):
        try:
            nickname = DiscordOAuthManager._sanitize_name(nickname)
            custom_headers = {'content-type': 'application/json', 'authorization': 'Bot ' + settings.DISCORD_BOT_TOKEN}
            data = {'nick': nickname}
            path = DISCORD_URL + "/guilds/" + str(settings.DISCORD_GUILD_ID) + "/members/" + str(user_id)
            r = requests.patch(path, headers=custom_headers, json=data)
            logger.debug("Got status code %s after setting nickname for Discord user ID %s (%s)" % (
                r.status_code, user_id, nickname))
            if r.status_code == 404:
                logger.warn("Discord user ID %s could not be found in server." % user_id)
                return True
            r.raise_for_status()
            return True
        except:
            logger.exception("Failed to set nickname for Discord user ID %s (%s)" % (user_id, nickname))
            return False

    @staticmethod
    def delete_user(user_id):
        try:
            custom_headers = {'accept': 'application/json', 'authorization': 'Bot ' + settings.DISCORD_BOT_TOKEN}
            path = DISCORD_URL + "/guilds/" + str(settings.DISCORD_GUILD_ID) + "/members/" + str(user_id)
            r = requests.delete(path, headers=custom_headers)
            logger.debug("Got status code %s after removing Discord user ID %s" % (r.status_code, user_id))
            if r.status_code == 404:
                logger.warn("Discord user ID %s already left the server." % user_id)
                return True
            r.raise_for_status()
            return True
        except:
            logger.exception("Failed to remove Discord user ID %s" % user_id)
            return False

    @staticmethod
    def _get_groups():
        custom_headers = {'accept': 'application/json', 'authorization': 'Bot ' + settings.DISCORD_BOT_TOKEN}
        path = DISCORD_URL + "/guilds/" + str(settings.DISCORD_GUILD_ID) + "/roles"
        r = requests.get(path, headers=custom_headers)
        logger.debug("Got status code %s after retrieving Discord roles" % r.status_code)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _generate_cache_role_key(name):
        return 'DISCORD_ROLE_NAME__%s' % md5(str(name).encode('utf-8')).hexdigest()

    @staticmethod
    def _group_name_to_id(name):
        name = DiscordOAuthManager._sanitize_groupname(name)

        def get_or_make_role():
            groups = DiscordOAuthManager._get_groups()
            for g in groups:
                if g['name'] == name:
                    return g['id']
            return DiscordOAuthManager._create_group(name)['id']
        return cache.get_or_set(DiscordOAuthManager._generate_cache_role_key(name), get_or_make_role, GROUP_CACHE_MAX_AGE)

    @staticmethod
    def __generate_role():
        custom_headers = {'accept': 'application/json', 'authorization': 'Bot ' + settings.DISCORD_BOT_TOKEN}
        path = DISCORD_URL + "/guilds/" + str(settings.DISCORD_GUILD_ID) + "/roles"
        r = requests.post(path, headers=custom_headers)
        logger.debug("Received status code %s after generating new role." % r.status_code)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def __edit_role(role_id, name, color=0, hoist=True, permissions=36785152):
        custom_headers = {'content-type': 'application/json', 'authorization': 'Bot ' + settings.DISCORD_BOT_TOKEN}
        data = {
            'color': color,
            'hoist': hoist,
            'name': name,
            'permissions': permissions,
        }
        path = DISCORD_URL + "/guilds/" + str(settings.DISCORD_GUILD_ID) + "/roles/" + str(role_id)
        r = requests.patch(path, headers=custom_headers, data=json.dumps(data))
        logger.debug("Received status code %s after editing role id %s" % (r.status_code, role_id))
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _create_group(name):
        role = DiscordOAuthManager.__generate_role()
        return DiscordOAuthManager.__edit_role(role['id'], name)

    @staticmethod
    @api_backoff
    def update_groups(user_id, groups):
        custom_headers = {'content-type': 'application/json', 'authorization': 'Bot ' + settings.DISCORD_BOT_TOKEN}
        group_ids = [DiscordOAuthManager._group_name_to_id(DiscordOAuthManager._sanitize_groupname(g)) for g in groups]
        path = DISCORD_URL + "/guilds/" + str(settings.DISCORD_GUILD_ID) + "/members/" + str(user_id)
        data = {'roles': group_ids}
        r = requests.patch(path, headers=custom_headers, json=data)
        logger.debug("Received status code %s after setting user roles" % r.status_code)
        r.raise_for_status()

