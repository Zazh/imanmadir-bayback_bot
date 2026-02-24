"""
Safe migration: BonusMessage FK from BonusUser → TelegramUser, then delete BonusUser.

Steps:
1. Add temp nullable FK to TelegramUser
2. Data migration: copy BonusUser data to TelegramUser, link messages
3. Remove old FK, rename temp FK, delete BonusUser
"""
import django.db.models.deletion
from django.db import migrations, models


def migrate_bonus_users(apps, schema_editor):
    """For each BonusUser, find or create TelegramUser and relink messages."""
    BonusUser = apps.get_model('bonus', 'BonusUser')
    TelegramUser = apps.get_model('account', 'TelegramUser')
    BonusMessage = apps.get_model('bonus', 'BonusMessage')

    for bu in BonusUser.objects.all():
        tu, created = TelegramUser.objects.get_or_create(
            telegram_id=bu.telegram_id,
            defaults={
                'username': bu.username,
                'first_name': bu.first_name,
                'last_name': bu.last_name,
                'language_code': bu.language_code,
            },
        )
        if not created and bu.language_code and not tu.language_code:
            tu.language_code = bu.language_code
            tu.save(update_fields=['language_code'])

        BonusMessage.objects.filter(user_id=bu.pk).update(temp_user_id=tu.pk)


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0002_add_language_code'),
        ('bonus', '0001_initial'),
    ]

    operations = [
        # 1. Add temp FK to TelegramUser (nullable)
        migrations.AddField(
            model_name='bonusmessage',
            name='temp_user',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='+',
                to='account.telegramuser',
            ),
        ),

        # 2. Data migration
        migrations.RunPython(migrate_bonus_users, migrations.RunPython.noop),

        # 3. Remove old FK (to BonusUser)
        migrations.RemoveField(
            model_name='bonusmessage',
            name='user',
        ),

        # 4. Rename temp_user → user
        migrations.RenameField(
            model_name='bonusmessage',
            old_name='temp_user',
            new_name='user',
        ),

        # 5. Make FK non-nullable and set related_name
        migrations.AlterField(
            model_name='bonusmessage',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='bonus_messages',
                to='account.telegramuser',
                verbose_name='Пользователь',
            ),
        ),

        # 6. Update meta
        migrations.AlterModelOptions(
            name='bonusmessage',
            options={
                'ordering': ['created_at'],
                'verbose_name': 'Сообщение бонус-бота',
                'verbose_name_plural': 'Сообщения бонус-бота',
            },
        ),

        # 7. Delete BonusUser model
        migrations.DeleteModel(
            name='BonusUser',
        ),
    ]
