import strawberry

from users.schema import UsersQuery


@strawberry.type
class Query(UsersQuery):
    pass


schema = strawberry.Schema(query=Query)
