from __future__ import unicode_literals
from django.utils.encoding import python_2_unicode_compatible
from django.db import models
from django.contrib.auth.models import User, Permission
from authentication.managers import CharacterOwnershipManager, StateManager
from eveonline.models import EveCharacter, EveCorporationInfo, EveAllianceInfo
from notifications import notify
from django.utils.translation import ugettext_lazy as _
import logging

logger = logging.getLogger(__name__)


@python_2_unicode_compatible
class State(models.Model):
    name = models.CharField(max_length=20, unique=True)
    permissions = models.ManyToManyField(Permission, blank=True)
    priority = models.IntegerField(unique=True,
                                   help_text="Users get assigned the state with the highest priority available to them.")

    member_characters = models.ManyToManyField(EveCharacter, blank=True,
                                               help_text="Characters to which this state is available.")
    member_corporations = models.ManyToManyField(EveCorporationInfo, blank=True,
                                                 help_text="Corporations to whose members this state is available.")
    member_alliances = models.ManyToManyField(EveAllianceInfo, blank=True,
                                              help_text="Alliances to whose members this state is available.")
    public = models.BooleanField(default=False, help_text="Make this state available to any character.")

    objects = StateManager()

    class Meta:
        ordering = ['-priority']

    def __str__(self):
        return self.name

    def available_to_character(self, character):
        return self in State.objects.available_to_character(character)

    def available_to_user(self, user):
        return self in State.objects.available_to_user(user)


def get_guest_state():
    try:
        return State.objects.get(name='Guest')
    except State.DoesNotExist:
        return State.objects.create(name='Guest', priority=0, public=True)


def get_guest_state_pk():
    return get_guest_state().pk


@python_2_unicode_compatible
class UserProfile(models.Model):
    class Meta:
        default_permissions = ('change',)

    user = models.OneToOneField(User, related_name='profile', on_delete=models.CASCADE)
    main_character = models.OneToOneField(EveCharacter, blank=True, null=True, on_delete=models.SET_NULL)
    state = models.ForeignKey(State, on_delete=models.SET(get_guest_state), default=get_guest_state_pk)

    def assign_state(self, commit=True):
        state = State.objects.get_for_user(self.user)
        if self.state != state:
            self.state = state
            if commit:
                logger.info('Updating {} state to {}'.format(self.user, self.state))
                self.save(update_fields=['state'])
                notify(self.user, _('State Changed'),
                       _('Your user state has been changed to %(state)s') % ({'state': state}),
                       'info')

    def __str__(self):
        return str(self.user)


@python_2_unicode_compatible
class CharacterOwnership(models.Model):
    class Meta:
        default_permissions = ('change', 'delete')

    character = models.OneToOneField(EveCharacter, on_delete=models.CASCADE, related_name='character_ownership')
    owner_hash = models.CharField(max_length=28, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='character_ownerships')

    objects = CharacterOwnershipManager()

    def __str__(self):
        return "%s: %s" % (self.user, self.character)
