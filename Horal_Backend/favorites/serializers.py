from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from .models import FavoriteItem, Favorites
from products.models import (
    ProductVariant, ChildrenProduct, VehicleProduct,
    FashionProduct, GadgetProduct, ElectronicsProduct,
    AccessoryProduct, FoodProduct, HealthAndBeautyProduct,
)
from products.models import ProductIndex


CATEGORY_MODELS = {
    'children': ChildrenProduct,
    'vehicles': VehicleProduct,
    'fashion': FashionProduct,
    'gadget': GadgetProduct,
    'electronics': ElectronicsProduct,
    'accessory': AccessoryProduct,
    'foods': FoodProduct,
    'health and beauty': HealthAndBeautyProduct
}


class FavoriteItemSerializer(serializers.ModelSerializer):
    """Serializer for favorite items"""
    product = serializers.SerializerMethodField()

    class Meta:
        model = FavoriteItem
        fields = ['id', 'product', 'added_at']
        read_only_fields = ['id', 'product', 'added_at']

    def get_product(self, obj):
        """Method to get product details"""
        product = obj.product

        # Determine if there are variants available
        content_type = ContentType.objects.get_for_model(product)
        variants = ProductVariant.objects.filter(
            content_type=content_type,
            object_id=product.id
        )
        has_variants = variants.exists()

        # Get first product image if available
        image_url = None
        if hasattr(product, 'images'):
            images = product.images.all()
            if images.exists():
                image_url = images.first().url

        return {
            'id': str(product.id),
            'title': product.title,
            'price': str(product.price),
            'category': product.category.name if hasattr(product, 'category') else None,
            'subcategory': product.sub_category.name if hasattr(product, 'sub_category') else None,
            'type': product.__class__.__name__,
            'image_url': image_url,
            'has_variants': has_variants,
        }
    

class FavoritesSerializer(serializers.ModelSerializer):
    """Serializer for the favorites collection"""
    items = FavoriteItemSerializer(many=True, read_only=True)

    class Meta:
        model = Favorites
        fields = ['id', 'created_at', 'items']


class AddToFavoritesSerializer(serializers.Serializer):
    """Serializer for adding product to favorites"""
    product_id = serializers.UUIDField()

    def validate(self, data):
        """Validate product exists in ProductIndex"""
        product_id = data['product_id']
        try:
            product_index = ProductIndex.objects.get(id=product_id)
            data['product_index'] = product_index
            return data
        except ProductIndex.DoesNotExist:
            raise serializers.ValidationError(f"Product with ID {product_id} not found.")

    def create(self, validated_data):
        request = self.context['request']

        if request.user.is_authenticated:
            favorites, _ = Favorites.objects.get_or_create(user=request.user)
        else:
            session_key = request.session.session_key
            if not session_key:
                request.session.create()
                session_key = request.session.session_key
            favorites, _ = Favorites.objects.get_or_create(session_key=session_key)

        product_index = validated_data['product_index']

        favorite_item, _ = FavoriteItem.objects.get_or_create(
            favorites=favorites,
            product_index=product_index
        )

        return favorite_item