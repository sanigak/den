# DOC: configuration#local-settings
$env:DEN_ENV = 'development'
$env:DEN_DATA_DIR = Join-Path $PSScriptRoot 'local-data'
$env:DEN_OWNERS_FILE = Join-Path $PSScriptRoot 'household-owners.json'
$env:DEN_DISPLAY_TIME_ZONE = 'America/New_York'
# Optional private HTTPS bookmark; leave empty for local development.
$env:DEN_PUBLIC_ORIGIN = ''
# Set DEN_SECRET_FILE to a private JSON file when enabling optional AI.
$env:DEN_AI_ENABLED = '0'
