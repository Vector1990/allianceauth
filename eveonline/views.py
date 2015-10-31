from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import permission_required

from util import add_member_permission
from util import remove_member_permission
from util import check_if_user_has_permission
from forms import UpdateKeyForm
from managers import EveManager
from authentication.managers import AuthServicesInfoManager
from services.managers.eve_api_manager import EveApiManager
from util.common_task import add_user_to_group
from util.common_task import remove_user_from_group
from util.common_task import deactivate_services
from util.common_task import generate_corp_group_name
from eveonline.models import EveCorporationInfo
from eveonline.models import EveCharacter
from eveonline.models import EveApiKeyPair
from authentication.models import AuthServicesInfo


def disable_member(user, char_id):
    remove_member_permission(user, 'member')
    remove_user_from_group(user, settings.DEFAULT_AUTH_GROUP)
    remove_user_from_group(user,
                           generate_corp_group_name(
                               EveManager.get_character_by_id(char_id).corporation_name))
    deactivate_services(user)


def disable_blue_member(user):
    remove_member_permission(user, 'blue_member')
    remove_user_from_group(user, settings.DEFAULT_BLUE_GROUP)
    deactivate_services(user)


@login_required
def add_api_key(request):
    if request.method == 'POST':
        form = UpdateKeyForm(request.POST)

        if form.is_valid():
            EveManager.create_api_keypair(form.cleaned_data['api_id'],
                                          form.cleaned_data['api_key'],
                                          request.user)

            # Grab characters associated with the key pair
            characters = EveApiManager.get_characters_from_api(form.cleaned_data['api_id'],
                                                               form.cleaned_data['api_key'])
            EveManager.create_characters_from_list(characters, request.user, form.cleaned_data['api_id'])
            return HttpResponseRedirect("/api_key_management/")
    else:
        form = UpdateKeyForm()
    context = {'form': form, 'apikeypairs': EveManager.get_api_key_pairs(request.user.id)}
    return render_to_response('registered/addapikey.html', context,
                              context_instance=RequestContext(request))


@login_required
def api_key_management_view(request):
    context = {'apikeypairs': EveManager.get_api_key_pairs(request.user.id)}

    return render_to_response('registered/apikeymanagment.html', context,
                              context_instance=RequestContext(request))


@login_required
def api_key_removal(request, api_id):
    authinfo = AuthServicesInfoManager.get_auth_service_info(request.user)
    # Check if our users main id is in the to be deleted characters
    characters = EveManager.get_characters_by_owner_id(request.user.id)
    if characters is not None:
        for character in characters:
            if character.character_id == authinfo.main_char_id:
                if character.api_id == api_id:
                    # TODO: Remove servies also
                    if authinfo.is_blue:
                        disable_blue_member(request.user)
                    else:
                        disable_member(request.user, authinfo.main_char_id)

    EveManager.delete_api_key_pair(api_id, request.user.id)
    EveManager.delete_characters_by_api_id(api_id, request.user.id)

    return HttpResponseRedirect("/api_key_management/")


@login_required
def characters_view(request):
    render_items = {'characters': EveManager.get_characters_by_owner_id(request.user.id),
                    'authinfo': AuthServicesInfoManager.get_auth_service_info(request.user)}
    return render_to_response('registered/characters.html', render_items, context_instance=RequestContext(request))


@login_required
def main_character_change(request, char_id):
    if EveManager.check_if_character_owned_by_user(char_id, request.user):
        previousmainid = AuthServicesInfoManager.get_auth_service_info(request.user).main_char_id
        AuthServicesInfoManager.update_main_char_Id(char_id, request.user)
        # Check if character is in the alliance
        character_info = EveManager.get_character_by_id(char_id)
        corporation_info = EveManager.get_corporation_info_by_id(character_info.corporation_id)

        if (settings.IS_CORP and EveManager.get_charater_corporation_id_by_id(char_id) == settings.CORP_ID) or (not settings.IS_CORP and EveManager.get_charater_alliance_id_by_id(char_id) == settings.ALLIANCE_ID):
            add_member_permission(request.user, 'member')
            add_user_to_group(request.user, settings.DEFAULT_AUTH_GROUP)
            add_user_to_group(request.user,
                              generate_corp_group_name(EveManager.get_character_by_id(char_id).corporation_name))

        elif corporation_info != None:
            if corporation_info.is_blue:
                add_member_permission(request.user, 'blue_member')
                add_user_to_group(request.user, settings.DEFAULT_BLUE_GROUP)
                AuthServicesInfoManager.update_is_blue(True, request.user)
            else:
                if check_if_user_has_permission(request.user, 'member'):
                    disable_member(request.user, previousmainid)

                if check_if_user_has_permission(request.user, 'blue_member'):
                    disable_blue_member(request.user)
        else:
            # TODO: disable serivces
            if check_if_user_has_permission(request.user, 'member'):
                disable_member(request.user, previousmainid)

            if check_if_user_has_permission(request.user, 'blue_member'):
                disable_blue_member(request.user)

        return HttpResponseRedirect("/characters")
    return HttpResponseRedirect("/characters")


@login_required
@permission_required('auth.corp_stats')
def corp_stats_view(request):
    # Get the corp the member is in
    auth_info = AuthServicesInfo.objects.get(user=request.user)
    main_char = EveCharacter.objects.get(character_id=auth_info.main_char_id)
    corp = EveCorporationInfo.objects.get(corporation_id=main_char.corporation_id)
    current_count = 0
    allcharacters = {}
    all_characters = EveCharacter.objects.all()
    for char in all_characters:
        if char:
            try:
                if char.corporation_id == corp.corporation_id:
                    current_count = current_count + 1
                    allcharacters[char.character_name] = EveApiKeyPair.objects.get(api_id=char.api_id)
            except:
                pass

    context = {"corp": corp,
               "currentCount": current_count,
               "characters": allcharacters}

    return render_to_response('registered/corpstats.html', context, context_instance=RequestContext(request))
