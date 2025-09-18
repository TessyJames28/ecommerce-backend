from users.models import CustomUser
from sellers.models import SellerKYC

users = CustomUser.objects.all()
sellers = SellerKYC.objects.all()

print(f"Users: {users}\nUser Count: {users.count()}")
print(f"Sellers: {sellers}\nSeller Count: {sellers.count()}")