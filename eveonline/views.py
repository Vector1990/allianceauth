from __future__ import unicode_literals
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from eveonline.forms import UpdateKeyForm
from eveonline.managers import EveManager
from authentication.managers import AuthServicesInfoManager
from services.managers.eve_api_manager import EveApiManager
from eveonline.models import EveApiKeyPair, EveCharacter
from authentication.models import AuthServicesInfo
from authentication.tasks import set_state
from eveonline.tasks import refresh_api

from eve_sso.decorators import token_required
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@login_required
def add_api_key(request):
    logger.debug("add_api_key called by user %s" % request.user)
    if request.method == 'POST':
        form = UpdateKeyForm(request.user, request.POST)
        logger.debug("Request type POST with form valid: %s" % form.is_valid())
        if form.is_valid():
            if EveApiKeyPair.objects.filter(api_id=form.cleaned_data['api_id'],
                                            api_key=form.cleaned_data['api_key']).exists():
                # allow orphaned keys to proceed to SSO validation upon re-entry
                api_key = EveApiKeyPair.objects.get(api_id=form.cleaned_data['api_id'],
                                                   api_key=form.cleaned_data['api_key'])
            elif EveApiKeyPair.objects.filter(api_id=form.cleaned_data['api_id']).exists():
                logger.warn('API %s re-added with different vcode.' % form.cleaned_data['api_id'])
                EveApiKeyPair.objects.filter(api_id=form.cleaned_data['api_id']).delete()
                api_key = EveApiKeyPair.objects.create(api_id=form.cleaned_data['api_id'],
                                                       api_key=form.cleaned_data['api_key'])
            else:
                api_key = EveApiKeyPair.objects.create(api_id=form.cleaned_data['api_id'],
                                                       api_key=form.cleaned_data['api_key'])
            owner = None
            if not settings.API_SSO_VALIDATION:
                # set API and character owners if SSO validation not requested
                api_key.user = request.user
                api_key.save()
                owner = request.user
            # Grab characters associated with the key pair
            characters = EveApiManager.get_characters_from_api(form.cleaned_data['api_id'],
                                                               form.cleaned_data['api_key'])
            EveManager.create_characters_from_list(characters, owner, form.cleaned_data['api_id'])
            logger.info("Successfully processed api add form for user %s" % request.user)
            if not settings.API_SSO_VALIDATION:
                messages.success(request, 'Added API key %s to your account.' % form.cleaned_data['api_id'])
                auth = AuthServicesInfo.objects.get_or_create(user=request.user)[0]
                if not auth.main_char_id:
                    return redirect('auth_characters')
                return redirect("/api_key_management/")
            else:
                logger.debug('Requesting SSO validation of API %s by user %s' % (api_key.api_id, request.user))
                return render(request, 'registered/apisso.html', context={'api':api_key})
        else:
            logger.debug("Form invalid: returning to form.")
    else:
        logger.debug("Providing empty update key form for user %s" % request.user)
        form = UpdateKeyForm(request.user)
    context = {'form': form, 'apikeypairs': EveManager.get_api_key_pairs(request.user.id)}
    return render(request, 'registered/addapikey.html', context=context)


@login_required
@token_required(new=True)
def api_sso_validate(request, tokens, api_id):
    logger.debug('api_sso_validate called by user %s for api %s' % (request.user, api_id))
    api = get_object_or_404(EveApiKeyPair, api_id=api_id)
    if api.user:
        logger.warning('User %s attempting to take ownership of api %s from %s' % (request.user, api_id, api.user))
        messages.warning(request, 'API %s already claimed by user %s' % (api_id, api.user))
        return redirect('auth_api_key_management')
    token = tokens[0]
    logger.debug('API %s has no owner. Checking if token for %s matches.' % (api_id, token.character_name))
    characters = EveApiManager.get_characters_from_api(api.api_id, api.api_key).result
    if token.character_id in characters:
        api.user = request.user
        api.save()
        EveCharacter.objects.filter(character_id__in=characters).update(user=request.user, api_id=api_id)
        messages.success(request, 'Confirmed ownership of API %s' % api.api_id)
        auth, c = AuthServicesInfo.objects.get_or_create(user=request.user)
        if not auth.main_char_id:
            return redirect('auth_characters')
        return redirect('auth_api_key_management')
    else:
        messages.warning(request, '%s not found on API %s. Please SSO as a character on the API.' % (token.character_name, api.api_id))
    return render(request, 'registered/apisso.html', context={'api':api})
    

@login_required
def api_key_management_view(request):
    logger.debug("api_key_management_view called by user %s" % request.user)
    context = {'apikeypairs': EveManager.get_api_key_pairs(request.user.id)}

    return render(request, 'registered/apikeymanagment.html', context=context)


@login_required
def api_key_removal(request, api_id):
    logger.debug("api_key_removal called by user %s for api id %s" % (request.user, api_id))
    authinfo = AuthServicesInfo.objects.get_or_create(user=request.user)[0]
    EveManager.delete_api_key_pair(api_id, request.user.id)
    EveManager.delete_characters_by_api_id(api_id, request.user.id)
    messages.success(request, 'Deleted API key %s' % api_id)
    logger.info("Succesfully processed api delete request by user %s for api %s" % (request.user, api_id))
    if EveCharacter.objects.filter(character_id=authinfo.main_char_id).exists():
        return redirect("auth_api_key_management")
    else:
        authinfo.main_char_id = None
        authinfo.save()
        set_state(request.user)
        return redirect("auth_characters")


@login_required
def characters_view(request):
    logger.debug("characters_view called by user %s" % request.user)
    render_items = {'characters': EveManager.get_characters_by_owner_id(request.user.id),
                    'authinfo': AuthServicesInfo.objects.get_or_create(user=request.user)[0]}
    return render(request, 'registered/characters.html', context=render_items)


@login_required
def main_character_change(request, char_id):
    logger.debug("main_character_change called by user %s for character id %s" % (request.user, char_id))
    if EveManager.check_if_character_owned_by_user(char_id, request.user):
        AuthServicesInfoManager.update_main_char_id(char_id, request.user)
        messages.success(request, 'Changed main character ID to %s' % char_id)
        set_state(request.user)
        return redirect("auth_characters")
    messages.error(request, 'Failed to change main character - selected character is not owned by your account.')
    return redirect("auth_characters")


@login_required
def user_refresh_api(request, api_id):
    logger.debug("user_refresh_api called by user %s for api id %s" % (request.user, api_id))
    if EveApiKeyPair.objects.filter(api_id=api_id).exists():
        api_key_pair = EveApiKeyPair.objects.get(api_id=api_id)
        if api_key_pair.user == request.user:
            refresh_api(api_key_pair)
            messages.success(request, 'Refreshed API key %s' % api_id)
            set_state(request.user)
        else:
            messages.warning(request, 'You are not authorized to refresh that API key.')
            logger.warn("User %s not authorized to refresh api id %s" % (request.user, api_id))
    else:
        messages.warning(request, 'Unable to locate API key %s' % api_id)
        logger.warn("User %s unable to refresh api id %s - api key not found" % (request.user, api_id))
    return redirect("auth_api_key_management")
