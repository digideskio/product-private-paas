# ------------------------------------------------------------------------
#
# Copyright 2005-2015 WSO2, Inc. (http://wso2.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License
#
# ------------------------------------------------------------------------

from plugins.contracts import ICartridgeAgentPlugin
from modules.util.log import LogFactory
from modules.topology.topologycontext import TopologyContext
import subprocess
import os


class WSO2StartupHandler(ICartridgeAgentPlugin):
    """
    Configures and starts configurator, carbon server
    """
    log = LogFactory().get_log(__name__)

    # class constants
    CONST_PORT_MAPPINGS = "PORT_MAPPINGS"
    CONST_APPLICATION_ID = "APPLICATION_ID"
    CONST_MB_IP = "MB_IP"
    CONST_SERVICE_NAME = "SERVICE_NAME"
    CONST_CLUSTER_ID = "CLUSTER_ID"
    CONST_LB_IP = "LB_IP"
    CONST_WORKER = "worker"
    CONST_MANAGER = "manager"
    CONST_MGT = "mgt"

    CONST_PORT_MAPPING_MGT_HTTP_TRANSPORT = "mgt-http"
    CONST_PORT_MAPPING_MGT_HTTPS_TRANSPORT = "mgt-https"
    CONST_PORT_MAPPING_PT_HTTP_TRANSPORT = "pt-http"
    CONST_PORT_MAPPING_PT_HTTPS_TRANSPORT = "pt-https"
    CONST_PROTOCOL_HTTP = "http"
    CONST_PROTOCOL_HTTPS = "https"
    CONST_DEFAULT_CONFIG_PARAM_HOST_NAME = 'esb.wso2.com'
    CONST_DEFAULT_CONFIG_PARAM_MGT_HOST_NAME = 'mgt.esb.wso2.com'
    CONST_PPAAS_MEMBERSHIP_SCHEME = "private-paas"
    CONST_PRODUCT = "ESB"

    SERVICES = ["wso2esb-481-manager", "wso2esb-481-worker"]

    # list of environment variables exported by the plugin
    ENV_CONFIG_PARAM_SUB_DOMAIN = 'CONFIG_PARAM_SUB_DOMAIN'
    ENV_CONFIG_PARAM_MB_HOST = 'CONFIG_PARAM_MB_HOST'
    ENV_CONFIG_PARAM_CLUSTER_IDs = 'CONFIG_PARAM_CLUSTER_IDs'
    ENV_CONFIG_PARAM_HTTP_PROXY_PORT = 'CONFIG_PARAM_HTTP_PROXY_PORT'
    ENV_CONFIG_PARAM_HTTPS_PROXY_PORT = 'CONFIG_PARAM_HTTPS_PROXY_PORT'
    ENV_CONFIG_PARAM_PT_HTTP_PROXY_PORT = 'CONFIG_PARAM_PT_HTTP_PROXY_PORT'
    ENV_CONFIG_PARAM_PT_HTTPS_PROXY_PORT = 'CONFIG_PARAM_PT_HTTPS_PROXY_PORT'

    # clustering related environment variables read from payload_parameters
    ENV_CONFIG_PARAM_CLUSTERING = 'CONFIG_PARAM_CLUSTERING'
    ENV_CONFIG_PARAM_MEMBERSHIP_SCHEME = 'CONFIG_PARAM_MEMBERSHIP_SCHEME'
    ENV_CONFIG_PARAM_HOST_NAME = 'CONFIG_PARAM_HOST_NAME'
    ENV_CONFIG_PARAM_MGT_HOST_NAME = 'CONFIG_PARAM_MGT_HOST_NAME'

    def run_plugin(self, values):

        # read from 'values'
        port_mappings_str = values[self.CONST_PORT_MAPPINGS].replace("'", "")
        app_id = values[self.CONST_APPLICATION_ID]
        mb_ip = values[self.CONST_MB_IP]
        service_type = values[self.CONST_SERVICE_NAME]
        my_cluster_id = values[self.CONST_CLUSTER_ID]
        clustering = values.get(self.ENV_CONFIG_PARAM_CLUSTERING, 'false')
        membership_scheme = values.get(self.ENV_CONFIG_PARAM_MEMBERSHIP_SCHEME)
        host_name = values.get(self.ENV_CONFIG_PARAM_HOST_NAME, self.CONST_DEFAULT_CONFIG_PARAM_HOST_NAME)
        mgt_host_name = values.get(self.ENV_CONFIG_PARAM_MGT_HOST_NAME, self.CONST_DEFAULT_CONFIG_PARAM_MGT_HOST_NAME)
        lb_ip = values.get(self.CONST_LB_IP)

        # log above values
        WSO2StartupHandler.log.info("Port Mappings: %s" % port_mappings_str)
        WSO2StartupHandler.log.info("Application ID: %s" % app_id)
        WSO2StartupHandler.log.info("MB IP: %s" % mb_ip)
        WSO2StartupHandler.log.info("Service Name: %s" % service_type)
        WSO2StartupHandler.log.info("Cluster ID: %s" % my_cluster_id)
        WSO2StartupHandler.log.info("Clustering: %s" % clustering)
        WSO2StartupHandler.log.info("Membership Scheme: %s" % membership_scheme)
        WSO2StartupHandler.log.info("Host Name: %s" % host_name)
        WSO2StartupHandler.log.info("Mgt Host Name: %s" % mgt_host_name)
        WSO2StartupHandler.log.info("LB IP: %s" % lb_ip)

        # export Proxy Ports as Env. variables - used in catalina-server.xml
        mgt_http_proxy_port = self.read_proxy_port(port_mappings_str, self.CONST_PORT_MAPPING_MGT_HTTP_TRANSPORT,
                                                   self.CONST_PROTOCOL_HTTP)
        mgt_https_proxy_port = self.read_proxy_port(port_mappings_str, self.CONST_PORT_MAPPING_MGT_HTTPS_TRANSPORT,
                                                    self.CONST_PROTOCOL_HTTPS)
        pt_http_proxy_port = self.read_proxy_port(port_mappings_str, self.CONST_PORT_MAPPING_PT_HTTP_TRANSPORT,
                                                  self.CONST_PROTOCOL_HTTP)
        pt_https_proxy_port = self.read_proxy_port(port_mappings_str, self.CONST_PORT_MAPPING_PT_HTTPS_TRANSPORT,
                                                   self.CONST_PROTOCOL_HTTPS)
        self.export_env_var(self.ENV_CONFIG_PARAM_HTTP_PROXY_PORT, mgt_http_proxy_port)
        self.export_env_var(self.ENV_CONFIG_PARAM_HTTPS_PROXY_PORT, mgt_https_proxy_port)
        self.export_env_var(self.ENV_CONFIG_PARAM_PT_HTTP_PROXY_PORT, pt_http_proxy_port)
        self.export_env_var(self.ENV_CONFIG_PARAM_PT_HTTPS_PROXY_PORT, pt_https_proxy_port)

        # set sub-domain
        sub_domain = None
        if service_type.endswith(self.CONST_MANAGER):
            sub_domain = self.CONST_MGT
        elif service_type.endswith(self.CONST_WORKER):
            sub_domain = self.CONST_WORKER
        if sub_domain is not None:
            self.export_env_var(self.ENV_CONFIG_PARAM_SUB_DOMAIN, sub_domain)

        # update /etc/hosts - when cluster is fronted by an LB
        if lb_ip is not None and clustering == 'true':
            if host_name is not None:
                self.update_hosts_file(lb_ip, host_name)
            if mgt_host_name is not None:
                self.update_hosts_file(lb_ip, mgt_host_name)
        else:
            WSO2StartupHandler.log.warn("LB_IP is not set. Hence cluster might fail.")

        # if CONFIG_PARAM_MEMBERSHIP_SCHEME is not set, set the private-paas membership scheme as default one
        if membership_scheme is None:
            membership_scheme = self.CONST_PPAAS_MEMBERSHIP_SCHEME
            self.export_env_var(self.ENV_CONFIG_PARAM_MEMBERSHIP_SCHEME, membership_scheme)

        # check if clustering is enabled and membership scheme is set to 'private-paas'
        if clustering == 'true' and membership_scheme == self.CONST_PPAAS_MEMBERSHIP_SCHEME:
            # export Cluster_Ids as Env. variables - used in axis2.xml
            self.set_cluster_ids(app_id, service_type, my_cluster_id)
            # export mb_ip as Env.variable - used in jndi.properties
            if mb_ip is not None:
                self.export_env_var(self.ENV_CONFIG_PARAM_MB_HOST, mb_ip)

        # start configurator
        WSO2StartupHandler.log.info("Configuring WSO2 %s..." % self.CONST_PRODUCT)
        config_command = "python ${CONFIGURATOR_HOME}/configurator.py"
        env_var = os.environ.copy()
        p = subprocess.Popen(config_command, env=env_var, shell=True)
        output, errors = p.communicate()
        WSO2StartupHandler.log.info("WSO2 %s configured successfully" % self.CONST_PRODUCT)

        # start server
        WSO2StartupHandler.log.info("Starting WSO2 %s ..." % self.CONST_PRODUCT)
        if service_type.endswith(self.CONST_WORKER):
            start_command = "exec ${CARBON_HOME}/bin/wso2server.sh -DworkerNode=true start"
        else:
            start_command = "exec ${CARBON_HOME}/bin/wso2server.sh -Dsetup start"
        env_var = os.environ.copy()
        p = subprocess.Popen(start_command, env=env_var, shell=True)
        output, errors = p.communicate()
        WSO2StartupHandler.log.info("WSO2 %s started successfully" % self.CONST_PRODUCT)

    def set_cluster_ids(self, app_id, service_type, my_cluster_id):
        """
        Set clusterIds of services read from topology for worker manager instances
        else use own clusterId

        :return: void
        """
        cluster_ids = []
        if service_type.endswith(self.CONST_MANAGER) or service_type.endswith(self.CONST_WORKER):
            for service_name in self.SERVICES:
                cluster_id_of_service = self.read_cluster_id_of_service(service_name, app_id)
                if cluster_id_of_service is not None:
                    cluster_ids.append(cluster_id_of_service)
        else:
            cluster_ids.append(my_cluster_id)
        # If clusterIds are available, set them as environment variables
        if cluster_ids:
            cluster_ids_string = ",".join(cluster_ids)
            self.export_env_var(self.ENV_CONFIG_PARAM_CLUSTER_IDs, cluster_ids_string)

    def read_cluster_id_of_service(self, service_name, app_id):
        cluster_id = None
        clusters = None
        topology = TopologyContext().get_topology()

        if topology.service_exists(service_name):
            service = topology.get_service(service_name)
            clusters = service.get_clusters()
        else:
            WSO2StartupHandler.log.warn("[Service] %s is not available in topology" % service_name)

        if clusters is not None:
            for cluster in clusters:
                if cluster.app_id == app_id:
                    cluster_id = cluster.cluster_id

        return cluster_id

    def update_hosts_file(self, ip_address, host_name):
        """
        Updates /etc/hosts file with clustering hostnames

        :return: void
        """
        config_command = "echo %s  %s >> /etc/hosts" % (ip_address, host_name)
        env_var = os.environ.copy()
        p = subprocess.Popen(config_command, env=env_var, shell=True)
        output, errors = p.communicate()
        WSO2StartupHandler.log.info(
            "Successfully updated [ip_address] %s & [hostname] %s in etc/hosts" % (ip_address, host_name))

    def read_proxy_port(self, port_mappings_str, port_mapping_name, port_mapping_protocol):
        """
        returns proxy port of the requested port mapping

        :return: void
        """

        # port mappings format: NAME:mgt-http|PROTOCOL:http|PORT:30001|PROXY_PORT:0|TYPE:NodePort;
        #                       NAME:mgt-https|PROTOCOL:https|PORT:30002|PROXY_PORT:0|TYPE:NodePort;
        #                       NAME:pt-http|PROTOCOL:http|PORT:30003|PROXY_PORT:7280|TYPE:ClientIP;
        #                       NAME:pt-https|PROTOCOL:https|PORT:30004|PROXY_PORT:7243|TYPE:NodePort

        service_proxy_port = None
        if port_mappings_str is not None:
            port_mappings_array = port_mappings_str.split(";")
            if port_mappings_array:

                for port_mapping in port_mappings_array:
                    # WSO2StartupHandler.log.debug("port_mapping: %s" % port_mapping)
                    name_value_array = port_mapping.split("|")
                    name = name_value_array[0].split(":")[1]
                    protocol = name_value_array[1].split(":")[1]
                    proxy_port = name_value_array[3].split(":")[1]
                    # If PROXY_PORT is not set, set PORT as the proxy port (ex:Kubernetes),
                    if proxy_port == '0':
                        proxy_port = name_value_array[2].split(":")[1]

                    if name == port_mapping_name and protocol == port_mapping_protocol:
                        service_proxy_port = proxy_port

        return service_proxy_port

    def export_env_var(self, variable, value):
        """
        exports key value pairs as env. variables

        :return: void
        """
        if value is not None:
            os.environ[variable] = value
            WSO2StartupHandler.log.info("Exported environment variable %s: %s" % (variable, value))
        else:
            WSO2StartupHandler.log.warn("Could not export environment variable %s " % variable)
