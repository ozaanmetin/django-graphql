import graphene

# Import shop GraphQL types and services
from shop import graphql as shop_graphql


class Query(
    # apps queries
    shop_graphql.Query,
    graphene.ObjectType
):
    pass


class Mutation(
    # apps mutations
    shop_graphql.Mutation,
    graphene.ObjectType
):
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)