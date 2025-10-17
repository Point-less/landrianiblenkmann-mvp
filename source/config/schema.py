import strawberry

from users.schema import UsersQuery
from opportunities.schema import OpportunitiesQuery


@strawberry.type
class Query(UsersQuery, OpportunitiesQuery):
    pass


schema = strawberry.Schema(query=Query)
