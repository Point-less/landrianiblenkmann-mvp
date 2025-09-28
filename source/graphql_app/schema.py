import strawberry


@strawberry.type
class Query:
    @strawberry.field
    def hello(self) -> str:
        return "Hello from Strawberry!"


schema = strawberry.Schema(query=Query)
