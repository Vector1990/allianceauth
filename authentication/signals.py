from __future__ import unicode_literals
from django.db.models.signals import post_save, pre_delete, m2m_changed
from django.db.models import Q
from django.dispatch import receiver
from django.contrib.auth.models import User
from authentication.models import CharacterOwnership, UserProfile, get_guest_state, State
from services.tasks import validate_services
from esi.models import Token
from eveonline.managers import EveManager
from eveonline.models import EveCharacter
import logging

logger = logging.getLogger(__name__)


def trigger_state_check(state):
    # evaluate all current members to ensure they still have access
    for profile in state.userprofile_set.all():
        profile.assign_state()

    # we may now be available to others with lower states
    check_states = State.objects.filter(priority__lt=state.priority)
    for profile in UserProfile.objects.filter(state__in=check_states):
        if state.available_to_user(profile.user):
            profile.state = state
            profile.save(update_fields=['state'])


@receiver(m2m_changed, sender=State.member_characters.through)
def state_member_characters_changed(sender, instance, action, *args, **kwargs):
    if action.startswith('post_'):
        trigger_state_check(instance)


@receiver(m2m_changed, sender=State.member_corporations.through)
def state_member_corporations_changed(sender, instance, action, *args, **kwargs):
    if action.startswith('post_'):
        trigger_state_check(instance)


@receiver(m2m_changed, sender=State.member_alliances.through)
def state_member_alliances_changed(sender, instance, action, *args, **kwargs):
    if action.startswith('post_'):
        trigger_state_check(instance)


@receiver(post_save, sender=State)
def state_saved(sender, instance, *args, **kwargs):
    trigger_state_check(instance)


# Is there a smarter way to intercept pre_save with a diff main_character or state?
@receiver(post_save, sender=UserProfile)
def reassess_on_profile_save(sender, instance, created, *args, **kwargs):
    # catches post_save from profiles to trigger necessary service and state checks
    if not created:
        update_fields = kwargs.pop('update_fields', []) or []
        if 'state' not in update_fields:
            instance.assign_state()
        # TODO: how do we prevent running this twice on profile state change?
        validate_services(instance.user)


@receiver(post_save, sender=User)
def create_required_models(sender, instance, created, *args, **kwargs):
    # ensure all users have a model
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=Token)
def record_character_ownership(sender, instance, created, *args, **kwargs):
    if created:
        # purge ownership records if the hash or auth user account has changed
        CharacterOwnership.objects.filter(character__character_id=instance.character_id).exclude(Q(
            owner_hash=instance.character_owner_hash) & Q(user=instance.user)).delete()
        # create character if needed
        if EveCharacter.objects.filter(character_id=instance.character_id).exists() is False:
            EveManager.create_character(instance.character_id)
        char = EveCharacter.objects.get(character_id=instance.character_id)
        # check if we need to create ownership
        if instance.user and not CharacterOwnership.objects.filter(character__character_id=instance.character_id).exists():
            CharacterOwnership.objects.update_or_create(character=char,
                                                        defaults={'owner_hash': instance.character_owner_hash,
                                                                  'user': instance.user})


@receiver(pre_delete, sender=CharacterOwnership)
def validate_main_character(sender, instance, *args, **kwargs):
    if instance.user.profile.main_character == instance.character:
        # clear main character as user no longer owns them
        instance.user.profile.main_character = None
        instance.user.profile.save()


@receiver(pre_delete, sender=Token)
def validate_main_character_token(sender, instance, *args, **kwargs):
    if UserProfile.objects.filter(main_character__character_id=instance.character_id):
        if not Token.objects.filter(character_id=instance.character_id).filter(user=instance.user).exists():
            # clear main character as we can no longer verify ownership
            instance.user.profile.main_character = None
            instance.user.profile.save()


@receiver(post_save, sender=User)
def assign_state_on_reactivate(sender, instance, *args, **kwargs):
    # There's no easy way to trigger an action upon saving from pre_save signal
    # If we're saving a user and that user is in the Guest state, assume is_active was just set to True and assign state
    if instance.is_active and instance.profile.state == get_guest_state():
        instance.profile.assign_state()
