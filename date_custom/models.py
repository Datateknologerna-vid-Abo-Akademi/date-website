from django.db import models
from django.utils.translation import gettext_lazy as _


class MembershipSignupRequest(models.Model):
    full_name = models.CharField(
        _('Fullständigt namn'), max_length=100)
    birth_date = models.DateField(
        _('Födelsedag'), help_text="Format ÅÅÅÅ-MM-DD")
    matriculation_number = models.CharField(
        _('Matrikelnummer'), max_length=20)
    street_address = models.CharField(
        _('Gatuadress'), max_length=100)
    postal_code = models.CharField(
        _('Postnummer'), max_length=10)
    city = models.CharField(_('Postort'), max_length=50)
    phone_number = models.CharField(_('Telefonnummer'), max_length=30)
    email = models.EmailField(_('E-Post'))
    website = models.URLField(
        _('Hemsida'), help_text="Fullständig URL t.ex. https://example.com", blank=True, null=True)
    next_of_kin = models.CharField(
        _('Närmaste anhörig (Namn + telefonnummer)'), max_length=200)
    processor_speed = models.CharField(
        _('Processorhastighet'), max_length=50, blank=True, null=True)
    willing_to_work = models.BooleanField(
        _('Jag kan tänka mig att jobba för föreningen (styrelse, fester, annat)'))
    newsletter_consent = models.BooleanField(
        _('Jag vill inte ha informationsbrev (eller e-mail) om föreningens verksamhet'))
    personal_data_sharing_nonconsent = models.BooleanField(
        _('Mina personuppgifter får inte ges åt andra medlemmar utan mitt samtycke'))
    membership_type = models.CharField(_("Medlemstyp"),
                                       choices=(("ordinary", "Ordinarie medlem"), ("supporting", "Stödjande medlem")))
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey("members.Member", on_delete=models.CASCADE)
