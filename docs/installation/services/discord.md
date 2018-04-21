# Discord
## Overview
Discord is a web-based instant messaging client with voice. Kind of like TeamSpeak meets Slack meets Skype. It also has a standalone app for phones and desktop.

Discord is very popular amongst ad-hoc small groups and larger organizations seeking a modern technology. Alternative voice communications should be investigated for larger than small-medium groups for more advanced features.

## Setup

### Prepare Your Settings File
In your auth project's settings file, do the following:
 - Add `'allianceauth.services.modules.discord',` to your `INSTALLED_APPS` list
 - Append the following to the bottom of the settings file:


    # Discord Configuration
    DISCORD_GUILD_ID = ''
    DISCORD_CALLBACK_URL = ''
    DISCORD_APP_ID = ''
    DISCORD_APP_SECRET = ''
    DISCORD_BOT_TOKEN = ''
    DISCORD_SYNC_NAMES = False

### Creating a Server
Navigate to the [Discord site](https://discordapp.com/) and register an account, or log in if you have one already.

On the left side of the screen you’ll see a circle with a plus sign. This is the button to create a new server. Go ahead and do that, naming it something obvious.

Now retrieve the server ID [following this procedure.](https://support.discordapp.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID-)

Update your auth project's settings file, inputting the server ID as `DISCORD_GUILD_ID`

```eval_rst
.. note::
   If you already have a Discord server skip the creation step, but be sure to retrieve the server ID
```

### Registering an Application

Navigate to the [Discord Developers site.](https://discordapp.com/developers/applications/me) Press the plus sign to create a new application.

Give it a name and description relating to your auth site. Add a redirect to `https://example.com/discord/callback/`, substituting your domain. Press Create Application.

Update your auth project's settings file, inputting this redirect address as `DISCORD_CALLBACK_URL`

On the application summary page, press Create a Bot User.

Update your auth project's settings file with these pieces of information from the summary page:
 - From the App Details panel, `DISCORD_APP_ID` is the Client/Application ID
 - From the App Details panel, `DISCORD_APP_SECRET` is the Secret
 - From the App Bot Users panel, `DISCORD_BOT_TOKEN` is the Token

### Preparing Auth
Before continuing it is essential to run migrations and restart Gunicorn and Celery.

### Adding a Bot to the Server
Once created, navigate to the services page of your Alliance Auth install as the superuser account. At the top there is a big green button labelled Link Discord Server. Click it, then from the drop down select the server you created, and then Authorize.

This adds a new user to your Discord server with a `BOT` tag, and a new role with the same name as your Discord application. Don't touch either of these. If for some reason the bot loses permissions or is removed from the server, click this button again.

To manage roles, this bot role must be at the top of the hierarchy. Edit your Discord server, roles, and click and drag the role with the same name as your application to the top of the list. This role must stay at the top of the list for the bot to work.  Finally, the owner of the bot account must enable 2 Factor Authentication (this is required from Discord for kicking and modifying member roles).  If you are unsure what 2FA is or how to set it up, refer to [this support page](https://support.discordapp.com/hc/en-us/articles/219576828).  It is also recommended to force 2FA on your server (this forces any admins or moderators to have 2fa enabled to perform similar functions on discord).

Note that the bot will never appear online as it does not participate in chat channels.

### Linking Accounts
Instead of the usual account creation procedure, for Discord to work we need to link accounts to Alliance Auth. When attempting to enable the Discord service, users are redirected to the official Discord site to authenticate. They will need to create an account if they don't have one prior to continuing. Upon authorization, users are redirected back to Alliance Auth with an OAuth code which is used to join the Discord server.

### Syncing Nicknames
If you want users to have their Discord nickname changed to their in-game character name, set `DISCORD_SYNC_NAMES` to `True`

## Managing Roles
Once users link their accounts you’ll notice Roles get populated on Discord. These are the equivalent to Groups on every other service. The default permissions should be enough for members to use text and audio communications. Add more permissions to the roles as desired through the server management window.

## Troubleshooting

### "Unknown Error" on Discord site when activating service
This indicates your callback URL doesn't match. Ensure the `DISCORD_CALLBACK_URL` setting exactly matches the URL entered on the Discord developers site. This includes http(s), trailing slash, etc.