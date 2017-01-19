from __future__ import unicode_literals
from django.utils.encoding import python_2_unicode_compatible
from django.db import models
from django.contrib.auth.models import User


@python_2_unicode_compatible
class EveCharacter(models.Model):
    character_id = models.CharField(max_length=254, unique=True)
    character_name = models.CharField(max_length=254, unique=True)
    corporation_id = models.CharField(max_length=254)
    corporation_name = models.CharField(max_length=254)
    corporation_ticker = models.CharField(max_length=254)
    alliance_id = models.CharField(max_length=254, blank=True, null=True, default='')
    alliance_name = models.CharField(max_length=254, blank=True, null=True, default='')
    api_id = models.CharField(max_length=254)
    user = models.ForeignKey(User, blank=True, null=True)

    def __str__(self):
        return self.character_name


@python_2_unicode_compatible
class EveApiKeyPair(models.Model):
    api_id = models.CharField(max_length=254, unique=True)
    api_key = models.CharField(max_length=254)
    user = models.ForeignKey(User, blank=True, null=True)
    sso_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.api_id


@python_2_unicode_compatible
class EveAllianceInfo(models.Model):
    alliance_id = models.CharField(max_length=254, unique=True)
    alliance_name = models.CharField(max_length=254, unique=True)
    alliance_ticker = models.CharField(max_length=254)
    executor_corp_id = models.CharField(max_length=254)
    is_blue = models.BooleanField(default=False)

    def __str__(self):
        return self.alliance_name


@python_2_unicode_compatible
class EveCorporationInfo(models.Model):
    corporation_id = models.CharField(max_length=254, unique=True)
    corporation_name = models.CharField(max_length=254, unique=True)
    corporation_ticker = models.CharField(max_length=254)
    member_count = models.IntegerField()
    is_blue = models.BooleanField(default=False)
    alliance = models.ForeignKey(EveAllianceInfo, blank=True, null=True)

    def __str__(self):
        return self.corporation_name
