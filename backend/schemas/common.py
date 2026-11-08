from marshmallow import Schema, fields


class ErrorResponseSchema(Schema):
    error = fields.Str(required=True)
    message = fields.Str(required=True)
    details = fields.Dict(required=False)


class PaginationMetaSchema(Schema):
    total = fields.Int(required=True)
    limit = fields.Int(required=True)
    offset = fields.Int(required=True)
    has_more = fields.Bool(required=True)
