from products.models import ProductIndex
from shops.models import Shop
from sellers.models import SellerKYC

products = ProductIndex.objects.all().values_list("shop_id", flat=True)
unique_shops = list(set(products))

shops = Shop.objects.filter(id__in=unique_shops)

for shop in shops:
        seller = SellerKYC.objects.get(user=shop.owner)
        print(f"Seller Name: {seller.address.first_name} {seller.address.last_name}")
        print(f"\tShop name: {shop.name}\n\tPhone number: {seller.address.mobile}")
        prods = ProductIndex.objects.filter(shop=shop)
        for p in prods:
               if not p.is_published:
                      print(f"\t\tProduct Name: {p.title}.")
                      print(f"\t\tCategory: {p.category}.\n")

