class RecordIdConverter:
    regex = '[1-9][0-9]{0,18}'

    def to_python(self, value):
        number = int(value)
        if number > 9223372036854775807:
            raise ValueError
        return number

    def to_url(self, value):
        return str(value)
