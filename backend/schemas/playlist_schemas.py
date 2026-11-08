from marshmallow import Schema, fields, validate, pre_load


class CreatePlaylistSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    public = fields.Bool(load_default=False)
    description = fields.Str(load_default="", validate=validate.Length(max=300))


class UpdatePlaylistSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=100))
    public = fields.Bool()
    description = fields.Str(validate=validate.Length(max=300))


class ModifyTracksSchema(Schema):
    # Supporta sia "track_ids" sia "track_id" singolo (per retrocompatibilità o invio list)
    track_ids = fields.List(
        fields.Str(validate=validate.Length(min=1, max=100)),
        required=True,
        validate=validate.Length(min=1, max=500, error="Fornire tra 1 e 500 ID di traccia.")
    )

    @pre_load
    def normalize_track_ids(self, data, **kwargs):
        if not isinstance(data, dict):
            return data
        # Se viene passato "track_id" come lista o stringa singola, normalizza in "track_ids"
        if "track_ids" not in data and "track_id" in data:
            val = data["track_id"]
            data["track_ids"] = val if isinstance(val, list) else [val]
        return data


class LikedTracksQuerySchema(Schema):
    offset = fields.Int(load_default=0, validate=validate.Range(min=0))
    limit = fields.Int(load_default=20, validate=validate.Range(min=1, max=100))
    q = fields.Str(load_default="")
