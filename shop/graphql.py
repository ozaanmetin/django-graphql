import graphene
from graphene_django import DjangoObjectType
from django.db.models import Avg, Q
from django.contrib.auth import get_user_model
from graphql import GraphQLError
from decimal import Decimal
from shop import models


User = get_user_model()


# Types
# -------------------------------------------------

class UserType(DjangoObjectType):
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "stores",
            "orders"
        )


class StoreType(DjangoObjectType):
    total_products = graphene.Int()

    class Meta:
        model = models.Store
        fields = (
            "id",
            "name",
            "owner",
            "products"
        )

    def resolve_total_products(self, info):
        return self.products.count()


class ProductType(DjangoObjectType):
    average_rating = graphene.Float()
    review_count = graphene.Int()

    class Meta:
        model = models.Product
        fields = (
            "id",
            "name",
            "store",
            "price",
            "stock",
            "description",
            "reviews"
        )

    def resolve_average_rating(self, info):
        avg = self.reviews.aggregate(Avg('rating'))['rating__avg']
        return float(avg) if avg else None

    def resolve_review_count(self, info):
        return self.reviews.count()


class ReviewType(DjangoObjectType):
    class Meta:
        model = models.Review
        fields = (
            "id",
            "product",
            "user",
            "rating",
            "comment",
            "created_at"
        )


class OrderType(DjangoObjectType):
    class Meta:
        model = models.Order
        fields = (
            "id",
            "user",
            "total",
            "ordered_at",
            "items"
        )


class OrderItemType(DjangoObjectType):
    class Meta:
        model = models.OrderItem
        fields = (
            "id",
            "order",
            "product",
            "quantity",
            "price"
        )


# Input Types
# -------------------------------------------------


class CreateStoreInput(graphene.InputObjectType):
    name = graphene.String(required=True)


class CreateProductInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    store_id = graphene.Int(required=True)
    price = graphene.Decimal(required=True)
    stock = graphene.Int(default_value=0)
    description = graphene.String(default_value="")


class UpdateProductInput(graphene.InputObjectType):
    name = graphene.String()
    price = graphene.Decimal()
    stock = graphene.Int()
    description = graphene.String()


class CreateReviewInput(graphene.InputObjectType):
    product_id = graphene.Int(required=True)
    rating = graphene.Int(required=True)
    comment = graphene.String(required=True)


class OrderItemInput(graphene.InputObjectType):
    product_id = graphene.Int(required=True)
    quantity = graphene.Int(required=True)


# Queries
# -------------------------------------------------


class Query(graphene.ObjectType):
    # Users
    user = graphene.Field(UserType, id=graphene.Int())
    users = graphene.List(UserType)

    # Stores
    store = graphene.Field(StoreType, id=graphene.Int())
    stores = graphene.List(StoreType)

    # Products with filtering
    product = graphene.Field(ProductType, id=graphene.Int())
    products = graphene.List(
        ProductType,
        search=graphene.String(),
        store_id=graphene.Int(),
        min_price=graphene.Decimal(),
        max_price=graphene.Decimal(),
        first=graphene.Int(),
        offset=graphene.Int()
    )

    # Reviews
    review = graphene.Field(ReviewType, id=graphene.Int())
    reviews = graphene.List(ReviewType, product_id=graphene.Int())

    # Orders
    order = graphene.Field(OrderType, id=graphene.Int())
    orders = graphene.List(OrderType, user_id=graphene.Int())
    my_orders = graphene.List(OrderType)

    # User resolvers
    def resolve_user(self, info, id):
        try:
            return User.objects.get(id=id)
        except User.DoesNotExist:
            raise GraphQLError(f"User with id {id} not found")

    def resolve_users(self, info):
        return User.objects.all()

    # Store resolvers
    def resolve_store(self, info, id):
        try:
            return models.Store.objects.get(id=id)
        except models.Store.DoesNotExist:
            raise GraphQLError(f"Store with id {id} not found")

    def resolve_stores(self, info):
        return models.Store.objects.select_related("owner").prefetch_related("products").all()

    # Product resolvers
    def resolve_product(self, info, id):
        try:
            return models.Product.objects.select_related("store").prefetch_related("reviews").get(id=id)
        except models.Product.DoesNotExist:
            raise GraphQLError(f"Product with id {id} not found")

    def resolve_products(self, info, search=None, store_id=None, min_price=None, max_price=None, first=None, offset=None):
        queryset = models.Product.objects.select_related("store").prefetch_related("reviews").all()

        # Filtering
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )

        if store_id:
            queryset = queryset.filter(store_id=store_id)

        if min_price:
            queryset = queryset.filter(price__gte=min_price)

        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        # Pagination
        if offset:
            queryset = queryset[offset:]

        if first:
            queryset = queryset[:first]

        return queryset

    # Review resolvers
    def resolve_review(self, info, id):
        try:
            return models.Review.objects.get(id=id)
        except models.Review.DoesNotExist:
            raise GraphQLError(f"Review with id {id} not found")

    def resolve_reviews(self, info, product_id=None):
        queryset = models.Review.objects.select_related("user", "product").all()
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset

    # Order resolvers
    def resolve_order(self, info, id):
        try:
            return models.Order.objects.prefetch_related("items__product").get(id=id)
        except models.Order.DoesNotExist:
            raise GraphQLError(f"Order with id {id} not found")

    def resolve_orders(self, info, user_id=None):
        queryset = models.Order.objects.prefetch_related("items__product").all()
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        return queryset

    def resolve_my_orders(self, info):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")
        return models.Order.objects.filter(user=user).prefetch_related("items__product")


# Mutations
# -------------------------------------------------


class CreateStore(graphene.Mutation):
    class Arguments:
        input = CreateStoreInput(required=True)

    store = graphene.Field(StoreType)

    def mutate(self, info, input):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        store = models.Store.objects.create(
            name=input.name,
            owner=user
        )
        return CreateStore(store=store)


class UpdateStore(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        name = graphene.String(required=True)

    store = graphene.Field(StoreType)

    def mutate(self, info, id, name):
        user = info.context.user
        print(user)
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        try:
            store = models.Store.objects.get(id=id)
        except models.Store.DoesNotExist:
            raise GraphQLError(f"Store with id {id} not found")

        if store.owner != user:
            raise GraphQLError("You don't have permission to update this store")

        store.name = name
        store.save()
        return UpdateStore(store=store)


class DeleteStore(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    success = graphene.Boolean()

    def mutate(self, info, id):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        try:
            store = models.Store.objects.get(id=id)
        except models.Store.DoesNotExist:
            raise GraphQLError(f"Store with id {id} not found")

        if store.owner != user:
            raise GraphQLError("You don't have permission to delete this store")

        store.delete()
        return DeleteStore(success=True)


class CreateProduct(graphene.Mutation):
    class Arguments:
        input = CreateProductInput(required=True)

    product = graphene.Field(ProductType)

    def mutate(self, info, input):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        try:
            store = models.Store.objects.get(id=input.store_id)
        except models.Store.DoesNotExist:
            raise GraphQLError(f"Store with id {input.store_id} not found")

        if store.owner != user:
            raise GraphQLError("You don't have permission to add products to this store")

        if input.price < 0:
            raise GraphQLError("Price must be positive")

        if input.stock < 0:
            raise GraphQLError("Stock must be positive")

        product = models.Product.objects.create(
            name=input.name,
            store=store,
            price=input.price,
            stock=input.stock,
            description=input.description
        )
        return CreateProduct(product=product)


class UpdateProduct(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        input = UpdateProductInput(required=True)

    product = graphene.Field(ProductType)

    def mutate(self, info, id, input):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        try:
            product = models.Product.objects.select_related("store").get(id=id)
        except models.Product.DoesNotExist:
            raise GraphQLError(f"Product with id {id} not found")

        if product.store.owner != user:
            raise GraphQLError("You don't have permission to update this product")

        if input.name is not None:
            product.name = input.name
        if input.price is not None:
            if input.price < 0:
                raise GraphQLError("Price must be positive")
            product.price = input.price
        if input.stock is not None:
            if input.stock < 0:
                raise GraphQLError("Stock must be positive")
            product.stock = input.stock
        if input.description is not None:
            product.description = input.description

        product.save()
        return UpdateProduct(product=product)


class DeleteProduct(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    success = graphene.Boolean()

    def mutate(self, info, id):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        try:
            product = models.Product.objects.select_related("store").get(id=id)
        except models.Product.DoesNotExist:
            raise GraphQLError(f"Product with id {id} not found")

        if product.store.owner != user:
            raise GraphQLError("You don't have permission to delete this product")

        product.delete()
        return DeleteProduct(success=True)


class CreateReview(graphene.Mutation):
    class Arguments:
        input = CreateReviewInput(required=True)

    review = graphene.Field(ReviewType)

    def mutate(self, info, input):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        try:
            product = models.Product.objects.get(id=input.product_id)
        except models.Product.DoesNotExist:
            raise GraphQLError(f"Product with id {input.product_id} not found")

        if input.rating < 1 or input.rating > 5:
            raise GraphQLError("Rating must be between 1 and 5")

        # Check if user already reviewed this product
        if models.Review.objects.filter(product=product, user=user).exists():
            raise GraphQLError("You already reviewed this product")

        review = models.Review.objects.create(
            product=product,
            user=user,
            rating=input.rating,
            comment=input.comment
        )
        return CreateReview(review=review)


class UpdateReview(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        rating = graphene.Int()
        comment = graphene.String()

    review = graphene.Field(ReviewType)

    def mutate(self, info, id, rating=None, comment=None):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        try:
            review = models.Review.objects.get(id=id)
        except models.Review.DoesNotExist:
            raise GraphQLError(f"Review with id {id} not found")

        if review.user != user:
            raise GraphQLError("You don't have permission to update this review")

        if rating is not None:
            if rating < 1 or rating > 5:
                raise GraphQLError("Rating must be between 1 and 5")
            review.rating = rating

        if comment is not None:
            review.comment = comment

        review.save()
        return UpdateReview(review=review)


class DeleteReview(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    success = graphene.Boolean()

    def mutate(self, info, id):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        try:
            review = models.Review.objects.get(id=id)
        except models.Review.DoesNotExist:
            raise GraphQLError(f"Review with id {id} not found")

        if review.user != user:
            raise GraphQLError("You don't have permission to delete this review")

        review.delete()
        return DeleteReview(success=True)


class CreateOrder(graphene.Mutation):
    class Arguments:
        items = graphene.List(OrderItemInput, required=True)

    order = graphene.Field(OrderType)

    def mutate(self, info, items):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        if not items:
            raise GraphQLError("Order must have at least one item")

        # Calculate total and validate
        total = Decimal('0.00')
        order_items_data = []

        for item in items:
            try:
                product = models.Product.objects.get(id=item.product_id)
            except models.Product.DoesNotExist:
                raise GraphQLError(f"Product with id {item.product_id} not found")

            if item.quantity <= 0:
                raise GraphQLError("Quantity must be positive")

            if product.stock < item.quantity:
                raise GraphQLError(f"Not enough stock for {product.name}. Available: {product.stock}")

            item_total = product.price * item.quantity
            total += item_total

            order_items_data.append({
                'product': product,
                'quantity': item.quantity,
                'price': item_total
            })

        # Create order
        order = models.Order.objects.create(
            user=user,
            total=total
        )

        # Create order items and update stock
        for item_data in order_items_data:
            models.OrderItem.objects.create(
                order=order,
                product=item_data['product'],
                quantity=item_data['quantity'],
                price=item_data['price']
            )

            # Update stock
            product = item_data['product']
            product.stock -= item_data['quantity']
            product.save()

        return CreateOrder(order=order)


class Mutation(graphene.ObjectType):
    # Store mutations
    create_store = CreateStore.Field()
    update_store = UpdateStore.Field()
    delete_store = DeleteStore.Field()

    # Product mutations
    create_product = CreateProduct.Field()
    update_product = UpdateProduct.Field()
    delete_product = DeleteProduct.Field()

    # Review mutations
    create_review = CreateReview.Field()
    update_review = UpdateReview.Field()
    delete_review = DeleteReview.Field()

    # Order mutations
    create_order = CreateOrder.Field()
