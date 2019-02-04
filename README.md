## Usage

Edit the following fields in reset_pod.py

* TETRATION_URL = 'https://url'
* TETRATION_CREDS = './PATH/TO/api_credentials.json'

## Run from Python enabled CLI
For a partial clean-up.  Deletes workspaces and filters.
```
python reset_pod.py -t 'Pod01'
```

For a full clean-up.  Deletes workspaces, filters, scopes, and roles.
```
python reset_pod.py -t 'Pod01' --full
```