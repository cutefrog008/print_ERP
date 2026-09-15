from django.db.models.signals import post_save
from django.dispatch import receiver
from production.models import JobCosting
from delivery_challan.models import DeliveryChallanItem


@receiver(post_save, sender=JobCosting)
def update_challan_items_on_costing_change(sender, instance, created, **kwargs):
    new_cost = instance.grand_total
    DeliveryChallanItem.objects.filter(
        job_id=instance.job_id
    ).update(manual_cost_snapshot=new_cost)


@receiver(post_save, sender='delivery_challan.DeliveryChallanItem')
def sync_snapshot_from_job_on_item_save(sender, instance, created, **kwargs):
    if instance.job_id and (instance.manual_cost_snapshot is None or instance.manual_cost_snapshot == 0):
        try:
            from production.models import JobCosting
            costing = JobCosting.objects.filter(job_id=instance.job_id).first()
            if costing:
                DeliveryChallanItem.objects.filter(pk=instance.pk).update(
                    manual_cost_snapshot=costing.grand_total
                )
        except Exception:
            pass
