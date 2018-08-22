import json
from tetpyclient import RestClient
import argparse
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TETRATION_URL = 'https://url'
TETRATION_CREDS = './PATH/TO/api_credentials.json'

parser = argparse.ArgumentParser(description='Tetration API Demo Script')
parser.add_argument('-t','--tenant',help='Tenant Name', required=True)
args = vars(parser.parse_args())

restclient = RestClient(TETRATION_URL,
                credentials_file=TETRATION_CREDS,
                verify=False)

def reset_pod(restclient, vrf_id, app_scope_id, vrf_name):
    errors = []
    # -------------------------------------------------------------------------
    # FLUSH ANNOTATIONS
    # This API requires the scope *name* rather than an ID. In our case, the
    # name is the name of the VRF. We have to determine that programmatically.

    resp = restclient.post('/openapi/v1/assets/cmdb/flush/' + vrf_name)
    if resp.status_code == 200:
        print "[REMOVED] all user annotations for VRF '{}' using flush command".format(vrf_name)
    else:
        print "[ERROR] removing annotations for VRF '{}' using flush command.".format(vrf_name)
        errors.append("[ERROR] removing annotations for VRF '{}' using flush command.".format(vrf_name))
        print resp, resp.text


    # -------------------------------------------------------------------------
    # DETERMINE CHILD SCOPES WITH POTENTIAL WORKSPACES TO BE DELETED
    # Using two lists here as queues:
    # 1. toBeExamined is a FIFO where we add parent scopes at position zero and
    #    use pop to remove them from the end. We add one entire heirarchical
    #    level of parents before we add a single one of their children. This
    #    process will continue until there are no more children to add and the
    #    FIFO will eventually be empty.
    # 2. toBeDeleted is a LIFO where we append parent scopes at the end before
    #    we append their children. Later, we will pop scopes from the end when
    #    deleting them, so child scopes will always be deleted before their
    #    parents (which is required by Tetration).

    print "[CHECKING] all scopes in Tetration."
    toBeDeleted = []
    toBeExamined = [ app_scope_id ]
    while len(toBeExamined):
        scopeId = toBeExamined.pop()
        resp = restclient.get('/openapi/v1/app_scopes/' + scopeId)
        if resp.status_code == 200:
            for scope in resp.json()["child_app_scope_ids"]:
                toBeExamined.insert(0, scope)
                toBeDeleted.append(scope)
        else:
            print "[ERROR] examining scope '{}'. This will cause problems deleting all scopes.".format(scopeId)
            errors.append("[ERROR] examining scope '{}'. This will cause problems deleting all scopes.".format(scopeId))
            print resp, resp.text

    # -------------------------------------------------------------------------
    # DELETE THE WORKSPACES
    # Walk through all applications and remove any in a scope that should be
    # deleted. In order to delete an application, we have to turn off enforcing
    # and make it secondary first.

    resp = restclient.get('/openapi/v1/applications/')
    if resp.status_code == 200:
        resp_data = resp.json()
    else:
        print "[ERROR] reading application workspaces to determine which ones should be deleted."
        errors.append("[ERROR] reading application workspaces to determine which ones should be deleted.")
        print resp, resp.text
        resp_data = {}
    for app in resp_data:
        appName = app["name"]
        if app["app_scope_id"] in toBeDeleted or app["app_scope_id"] == app_scope_id:
            app_id = app["id"]
            # first we turn off enforcement
            if app["enforcement_enabled"]:
                r = restclient.post('/openapi/v1/applications/' + app_id + '/disable_enforce')
                if r.status_code == 200:
                    print "[CHANGED] app {} ({}) to not enforcing.".format(app_id, appName)
            # make the application secondary if it is primary
            if app["primary"]:
                req_payload = {"primary": "false"}
                r = restclient.put('/openapi/v1/applications/' + app_id, json_body=json.dumps(req_payload))
                if r.status_code == 200:
                    print "[CHANGED] app {} ({}) to secondary.".format(app_id, appName)
            # now delete the app
            r = restclient.delete('/openapi/v1/applications/' + app_id)
            if r.status_code == 200:
                print "[REMOVED] app {} ({}) successfully.".format(app_id, appName)

    # -------------------------------------------------------------------------
    # DELETE ALL FILTERS ASSOCIATED WITH THIS VRF_ID
    # Inventory filters have a query that the user enters but there is also a
    # query for the vrf_id to match. So we simply walk through all filters and
    # look for that query to match this vrf_id... if there is a match then
    # remove the inventory filter.

    resp = restclient.get('/openapi/v1/filters/inventories')
    if resp.status_code == 200:
        resp_data = resp.json()
    else:
        print "[ERROR] reading filters to determine which ones should be deleted."
        errors.append("[ERROR] reading filters to determine which ones should be deleted.")
        print resp, resp.text
        resp_data = {}
    for filt in resp_data:
        inventory_filter_id = filt["id"]
        filterName = filt["name"]
        for query in filt["query"]["filters"]:
            if 'field' in query.iterkeys() and query["field"] == "vrf_id" and query["value"] == int(vrf_id):
                r = restclient.delete('/openapi/v1/filters/inventories/' + inventory_filter_id)
                if r.status_code == 200:
                    print "[REMOVED] inventory filter {} named '{}'.".format(inventory_filter_id, filterName)
                else:
                    print "[ERROR] removing inventory filter {} named '{}'.".format(inventory_filter_id, filterName)
                    errors.append("[ERROR] removing inventory filter {} named '{}'.".format(inventory_filter_id, filterName))
                    print r, r.text

    return {'success':1,'errors':errors}

def get_root_scope(vrf_name):
    resp = restclient.get('/app_scopes')
    if resp.status_code == 200:
        app_scopes = [ scope for scope in resp.json() if scope['short_name'] == vrf_name]
        if len(app_scopes) > 0:
            return {'root_scope_id':app_scopes[0]['id'],'vrf_id':app_scopes[0]['short_query']['value']}
    
    print "[ERROR] retrieving scopes for tenant: {tenant}".format(tenant=vrf_name)
    return None

scope = get_root_scope(args['tenant'])
reset_pod(restclient=restclient,vrf_id=scope['vrf_id'],app_scope_id=scope['root_scope_id'],vrf_name=args['tenant'])
