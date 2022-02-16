#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2018, Ansible Project
# Copyright (c) 2018, Abhijeet Kasurde <akasurde@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
from re import M

#from plugins.modules.vmware_datastore_info import PyVmomiHelper
__metaclass__ = type


DOCUMENTATION = r'''
---
module: vmware_datastore_cluster_info
short_description: Gather information about  VMware vSphere datastore clusters
description:
    - This module can be used to gather information about VMware vSphere datastore clusters
    - All parameters and VMware object values are case sensitive.
author:
-  Carlos Tronco (@ctronco)
notes:
    - Tested on vSphere 6.0, 6.5
requirements:
    - "python >= 2.6"
    - PyVmomi
options:
    datacenter_name:
      description:
      - The name of the datacenter.
      - You must specify either a C(datacenter_name) or a C(folder).
      - Mutually exclusive with C(folder) parameter.
      required: False
      aliases: [ datacenter ]
      type: str
    datastore_cluster_name:
      description:
      - The name of the datastore cluster.
      required: False
      type: str
    folder:
      description:
      - Destination folder, absolute path to place datastore cluster in.
      - The folder should include the datacenter.
      - This parameter is case sensitive.
      - You must specify either a C(folder) or a C(datacenter_name).
      - 'Examples:'
      - '   folder: /datacenter1/datastore'
      - '   folder: datacenter1/datastore'
      - '   folder: /datacenter1/datastore/folder1'
      - '   folder: datacenter1/datastore/folder1'
      - '   folder: /folder1/datacenter1/datastore'
      - '   folder: folder1/datacenter1/datastore'
      - '   folder: /folder1/datacenter1/datastore/folder2'
      required: False
      type: str
extends_documentation_fragment:
- community.vmware.vmware.documentation

'''

EXAMPLES = r'''
- name: Gather Infor about all datastore clusters
  community.vmware.vmware_datastore_cluster_info:
    hostname: '{{ vcenter_hostname }}'
    username: '{{ vcenter_username }}'
    password: '{{ vcenter_password }}'
    datacenter_name: '{{ datacenter_name }}'
    datastore_cluster_name: '{{ datastore_cluster_name }}'
    enable_sdrs: True
    state: present
  delegate_to: localhost

- name: Gather Info about a particular cluster
  community.vmware.vmware_datastore_cluster_info:
    hostname: '{{ vcenter_hostname }}'
    username: '{{ vcenter_username }}'
    password: '{{ vcenter_password }}'
    folder: '/{{ datacenter_name }}/datastore/ds_folder'
    datastore_cluster_name: '{{ datastore_cluster_name }}'
    state: present
  delegate_to: localhost

- name: Delete datastore cluster
  community.vmware.vmware_datastore_cluster_info:
    hostname: '{{ vcenter_hostname }}'
    username: '{{ vcenter_username }}'
    password: '{{ vcenter_password }}'
    datacenter_name: '{{ datacenter_name }}'
    datastore_cluster_name: '{{ datastore_cluster_name }}'
    state: absent
  delegate_to: localhost
'''

RETURN = r'''
datastore_cluster_info:
    description: information about datastore cluster
    returned: always
    type: list
    sample: 
        [
            {
                    "datastores":[
                        "dsc_ds_01",
                        "dsc_ds_02",
                        "dsc_ds_03"
                    ],
                    datastoreClusterName : "dsc",
                    "sdrs_enabled": true,
                    "keep_vmdks_together": true,
                    "automation_level": "automated",
                    "load_balance_interval": 480,
                    "io_loadbalance_enabled":  true

            }
        ]
'''

try:
    from pyVmomi import vim
except ImportError:
    pass

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.vmware.plugins.module_utils.vmware import PyVmomi, vmware_argument_spec, wait_for_task, find_datastore_cluster_by_name,get_all_objs,get_parent_datacenter
from ansible.module_utils._text import to_native
from ansible_collections.community.vmware.plugins.module_utils.vmware_rest_client import VmwareRestClient


class VMwareDatastoreClusterInfo(PyVmomi):
    def __init__(self, module):
        super(VMwareDatastoreClusterInfo, self).__init__(module)
        self.folder= self.module.params['folder']
        #self.datacenter =self.module.params['datacenter']
        self.datastore_cluster_name = self.module.params['datastore_cluster_name']

        if self.folder:
            self.folder_obj = self.content.searchIndex.FindByInventoryPath(self.folder)
            if not self.folder_obj:
                self.module.fail_json(msg="Failed to find the folder specified by %(folder)s" % self.params)
        else:
            datacenter_name = self.params.get('datacenter_name')
            datacenter_obj = self.find_datacenter_by_name(datacenter_name)
            if not datacenter_obj:
                self.module.fail_json(msg="Failed to find datacenter '%s' required"
                                          " for managing datastore cluster." % datacenter_name)
            self.folder_obj = datacenter_obj.datastoreFolder

        self.datastore_cluster_name = self.params.get('datastore_cluster_name')
        self.datastore_cluster_obj = self.find_datastore_cluster_by_name(self.datastore_cluster_name)

    def get_datastore_cluster_info(self):
        self.datacenter_name = self.params.get('datacenter')
        results = dict(
            changed=False,
            datastore_cluster_info=[],
        )
        datacenter_objs = self.get_managed_objects_properties(vim_type=vim.Datacenter, properties=['name'])
        dcs = []
        for dc_obj in datacenter_objs:
            if len(dc_obj.propSet) == 1:
                if self.datacenter_name is not None:
                    if dc_obj.propSet[0].val == to_native(self.datacenter_name):
                        dcs.append(dc_obj.obj)
                        continue
                else:
                    dcs.append(dc_obj.obj)
    def build_datastore_cluster_list(self,datastore_cluster_list):
        """ build list of datastore clusters and relevant properties"""
        dscs = list()
        for dsc in datastore_cluster_list:
            temp_dsc =dict()
            summary = dsc.summary
            cfg = dsc.podStorageDrsEntry.storageDrsConfig
            temp_dsc['name'] = dsc.name
            temp_dsc['capacity'] = summary.capacity
            temp_dsc['capacity_gb'] = round(summary.capacity/1024**3,2)
            temp_dsc['capacity_tb'] = round(summary.capacity/1024**4,2)
            temp_dsc['free_space'] = summary.freeSpace
            temp_dsc['free_space_gb'] = round(summary.freeSpace/1024**3,2)
            temp_dsc['free_space_tb'] = round(summary.freeSpace/1024**4,2)
            temp_dsc['load_balance_interval'] = cfg.podConfig.loadBalanceInterval
            temp_dsc['load_balance_enabled'] = cfg.podConfig.ioLoadBalanceEnabled
            temp_dsc['sdrs_enabled'] = cfg.podConfig.enabled
            temp_dsc['sdrs_mode'] = cfg.podConfig.defaultVmBehavior
            temp_dsc['datastores'] = list()
            for ds in dsc.childEntity:
                ds_info = dict()
                ds_info['name'] = ds.name
                ds_info['free_space'] = ds.summary.freeSpace
                ds_info['free_space_gb'] = round(ds.summary.freeSpace/(1024**3),2)                
                ds_info['capacity'] = ds.summary.capacity
                ds_info['capacity_gb'] = round(ds.summary.capacity/(1024**3),2)
                ds_info['type'] = ds.summary.type
                # want to add moid at some point.... how? 
                temp_dsc['datastores'].extend([ds_info])
                
            json_dsc = self.to_json(temp_dsc)
            dscs.extend([json_dsc])
        return dscs
            



class PyVmomiCache(object):
    """ This class caches references to objects which are requested multiples times but not modified """

    def __init__(self, content, dc_name=None):
        self.content = content
        self.dc_name = dc_name
        self.clusters = {}
        self.parent_datacenters = {}

    def get_all_objs(self, content, types, confine_to_datacenter=True):
        """ Wrapper around get_all_objs to set datacenter context """
        objects = get_all_objs(content, types)
        if confine_to_datacenter:
            if hasattr(objects, 'items'):
                # resource pools come back as a dictionary
                for k, v in tuple(objects.items()):
                    parent_dc = get_parent_datacenter(k)
                    if parent_dc.name != self.dc_name:
                        del objects[k]
            else:
                # everything else should be a list
                objects = [x for x in objects if get_parent_datacenter(x).name == self.dc_name]

        return objects



class PyVmomiHelper(PyVmomi):
    """ This class gets datastore_clusters """

    def __init__(self, module):
        super(PyVmomiHelper, self).__init__(module)
        self.cache = PyVmomiCache(self.content, dc_name=self.params['datacenter_name'])

    def lookup_dscluster(self, confine_to_datacenter):
        """ Get datastore cluster vCenter server """
        datastore_clusters = self.cache.get_all_objs(self.content, [vim.StoragePod], confine_to_datacenter)
        return datastore_clusters

    def lookup_dscluster_by_cluster(self):
        """ Get datastorecluster(s) per computecluster """
        cluster = find_datastore_cluster_by_name(self.content, self.params['datastore_cluster_name'])
        if not cluster:
            self.module.fail_json(msg='Failed to find datastore cluster "%(datastore_cluster_name)s"' % self.params)
        return [cluster]
#        c_dc = cluster.datastore
#        return c_dc


def main():
    argument_spec = vmware_argument_spec()
    argument_spec.update(
        dict(
            datacenter_name=dict(type='str', required=False, aliases=['datacenter']),
            datastore_cluster_name=dict(type='str', required=False),
            #cluster=dict(type='str',required=False),
            folder=dict(type='str', required=False),
        )
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        mutually_exclusive=[
            ['datacenter_name', 'folder'],
        ],
        required_one_of=[
            ['datacenter_name', 'folder'],
        ]
    )
    result = dict(changed=False)
    pyv = PyVmomiHelper(module)
    if module.params['datastore_cluster_name']:
        dxs = pyv.lookup_dscluster_by_cluster()
    elif module.params['datacenter_name']:
       dxs = pyv.lookup_dscluster(confine_to_datacenter=True)
    else: 
       dxs = pyv.lookup_dscluster(confine_to_datacenter=False)

    vmware_dscluster = VMwareDatastoreClusterInfo(module)
    datastore_clusters = vmware_dscluster.build_datastore_cluster_list(dxs)

    result['datastore_clusters'] = datastore_clusters
    module.exit_json(**result)


if __name__ == '__main__':
    main()
