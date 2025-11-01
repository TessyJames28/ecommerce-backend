from users.models import CustomUser
from sellers.models import SellerKYC
from django.utils.timezone import now
from datetime import datetime

users = CustomUser.objects.all()
sellers = SellerKYC.objects.all()

print(f"Users: {users}\nUser Count: {users.count()}")
print(f"Sellers: {sellers}\nSeller Count: {sellers.count()}")

year = now().year

oct_start = datetime(year, 10, 1, tzinfo=now().tzinfo)
oct_end = datetime(year, 10, 31, 23, 59, 59, tzinfo=now().tzinfo)

oct_users = CustomUser.objects.filter(created_at__range=(oct_start, oct_end))
oct_sellers = SellerKYC.objects.filter(verified_at__range=(oct_start, oct_end))

print(f"Oct Users count: {oct_users.count()}")
print(f"Oct Sellers count: {oct_sellers.count()}")
