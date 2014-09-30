import argparse
import pycurl
import cStringIO
import json

parser = argparse.ArgumentParser(description='This script allow to configure network mapping')
parser.add_argument('-i',
                    '--fuel', 
                    help = 'Fuel node ip address',
                    type = str,
                    required = True)
parser.add_argument('-n',
                    '--node', 
                    help = 'Node id',
                    type = int, 
                    required = True)
parser.add_argument('-m',
                    '--mgmt', 
                    nargs='+',
                    type = str,
                    help='List of interfaces what assigned to management network', 
                    required=True)
parser.add_argument('-p',
                    '--public', 
                    nargs='+',
                    type = str,
                    help='List of interfaces what assigned to management network', 
                    required=True)

parser.add_argument('-s',
                    '--storage', 
                    nargs='+',
                    type = str,
                    help='Description for foo argument', 
                    required=False)

parser.add_argument('-f',
                    '--assign',
                    choices=['name','mac'],
                    type = str,
                    help='Type of assign, here you can use mac or name notation of interfaces', 
                    required=True)

parser.add_argument('-x',
                    '--mgmt_bond_mode', 
                    type = str,
                    help='Description for bar argument', 
                    required=False)
 
parser.add_argument('-y',
                    '--public_bond_mode', 
                    type = str,
                    help='Description for bar argument', 
                    required=False)

parser.add_argument('-z',
                    '--storage_bond_mode', 
                    help='Description for bar argument', 
                    required=False)
args = vars(parser.parse_args())

def assign_bond_iface(ngname, iface_list):
    global bond_counter
    slaves_code = "_".join(iface_list)
    if slaves_code not in node_interfaces_hash.keys():
        new_bond = json.loads(bond_template)
        new_bond['name'] = bond_base_name + str(bond_counter)
        bond_counter += 1
        new_bond['slaves'] = iface_list
        node_interfaces_hash[slaves_code] = new_bond
    #assign types of bond ifaces
    node_interfaces_hash[slaves_code]['mode'] = bond_mode_mapping_list[ngname]
    return [slaves_code]

def iface_name_mapping(iface_name):
    for hashname, iface in node_interfaces_hash.iteritems():
        if iface['type'] == 'bond':
            if iface_name in iface['slaves']:
                return hashname
    return iface_name

def assign_iface(ngname, iface):
    node_interfaces_hash[iface]['assigned_networks'].append(ngdata[ngname])

def get_admin_dev(interface):
    return interface.get('slaves').sort()[0] if interface.get('type') == 'bond' else interface.get('name')

def get_iface_name(value):
    return node_interfaces_hash[value].get('mac') if assign_type == 'mac' else value 

bond_template = '{"type":"bond","name":"ovs-bond","mode":"active-backup","assigned_networks":[],"slaves":[]}'

fuel_ip = args.get('fuel')
node_id = args.get('node')
assign_type = args.get('assign')

response = cStringIO.StringIO()

# get data from nailgun
input_curl = pycurl.Curl()
input_curl.setopt(input_curl.URL, "http://%s:8000/api/nodes/%i/interfaces" % (fuel_ip, node_id) )
input_curl.setopt(input_curl.WRITEFUNCTION, response.write)
input_curl.perform()
input_curl.close()

node_interfaces = json.loads(response.getvalue())
node_interfaces_hash = {}
assign_mapping_list = {}
ngdata = {}
bond_mode_mapping_list = {}
network_name_list = [ 'public', 'management']

bond_counter = 0
bond_base_name = 'ovs-bond'

# collect assigned ng to hash array
for interface in node_interfaces:
    for assigned_network in interface.get('assigned_networks'):
        ngname = assigned_network.get('name')
        if ngname == 'fuelweb_admin':
            admin_dev = get_admin_dev(interface)
        ngdata[ngname] = assigned_network
    interface['assigned_networks'] = []
    if interface.get('type') != 'bond':
        node_interfaces_hash[interface.get(assign_type)] = interface

# read info from cli options
for ngname in network_name_list:
    option = 'mgmt' if ngname == 'management' else ngname
    assign_mapping_list[ngname] = sorted([ get_iface_name(var) for var in args.get(option) ])
    bond_mode_mapping_list[ngname] = args.get(option + '_bond_mode')

# assign ng to ifaces
for ngname, ifaces in assign_mapping_list.iteritems():
    if len(ifaces) > 1:
        ifaces = assign_bond_iface(ngname, ifaces)
    assign_iface(ngname, ifaces[0])

#reassign admin iface
assign_iface('fuelweb_admin', iface_name_mapping(admin_dev))

#send data
output_curl = pycurl.Curl()
output_curl.setopt(pycurl.URL, "http://%s:8000/api/nodes/%i/interfaces" % (fuel_ip, node_id))
output_curl.setopt(pycurl.HTTPHEADER, ['Accept: application/json'])
output_curl.setopt(pycurl.POST, 1)
output_curl.setopt(pycurl.POSTFIELDS, json.dumps(node_interfaces_hash.values()))
output_curl.perform()
