class InvalidSRIDException(Exception):
    def __init__(self, epsg_code, issue=None):
        msg = f"Cannot migrate schematisation with model_settings.epsg_code={epsg_code}"
        if issue is not None:
            msg += f"; {issue}"
        super().__init__(msg)