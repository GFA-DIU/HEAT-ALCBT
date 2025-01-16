from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        from allauth.account.models import EmailAddress
        from accounts.models import CustomUser
        from encrypted_json_fields import encrypt_str
        
        super().ready()

        def decrypt_init(self, *args, **kwargs):
            """
            Encrypt the email address.
            """

            customUser = CustomUser.objects.get(user_id=self.user_id)
            self.email = customUser.email


        def encrypt_clean(self, *args, **kwargs):
            """
            Decrypt the email address.
            """
            super().clean()
            self.email = self.email.lower()
            self.email = encrypt_str(self.email)


        EmailAddress.__init__ = decrypt_init
        EmailAddress.clean = encrypt_clean
