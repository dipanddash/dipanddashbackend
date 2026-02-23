# Generated migration for SupportTicket model updates

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('foodbackend', '0017_coupon_order_coupon_discount_usercouponusage_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='supportticket',
            name='subject',
            field=models.CharField(default='Support Request', max_length=200),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='supportticket',
            name='description',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='supportticket',
            name='priority',
            field=models.CharField(
                choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')],
                default='medium',
                max_length=10
            ),
        ),
    ]
