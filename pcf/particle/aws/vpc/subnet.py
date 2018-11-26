# Copyright 2018 Capital One Services, LLC
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
# limitations under the License.

from pcf.core.aws_resource import AWSResource
from pcf.core import State
from pcf.util import pcf_util
from pcf.particle.aws.vpc.vpc import VPC


class Subnet(AWSResource):
    """
    This is the implementation of Amazon's Subnet resource.
    """

    flavor = "subnet"
    state_lookup = {
        "available": State.running,
        "pending": State.pending,
        "missing": State.terminated
    }
    equivalent_states = {
        State.running: 1,
        State.stopped: 0,
        State.terminated: 0
    }

    START_PARAMS = {
        "CidrBlock",
        "AvailabilityZone",
        "Ipv6CidrBlock",
        "VpcId"
    }

    UNIQUE_KEYS = ["aws_resource.custom_config.subnet_name"]

    def __init__(self, particle_definition):
        super(Subnet, self).__init__(particle_definition, "ec2")
        self._set_unique_keys()
        self.subnet_name = self.custom_config.get("subnet_name")
        self._subnet_client = None

    @property
    def subnet_client(self):
        """
        The VPC client. Calls _get_vpc_client to create a new client if needed

        Returns:
             vpc_client
        """
        if not self._subnet_client:
            self._subnet_client = self._get_subnet_client()
        return self._subnet_client

    def _set_vpc_id(self):
        """
        Checks to see if user specified a vpcid in the particle definition. If not the vpc_id is retrieved from it's parent.
        If there is no parent vpc particle an exception is returned since a vpcid is required for creating a new subnet.

        """
        if not self.desired_state_definition.get("VpcId"):
            if len(self.parents) > 0:
                vpc_parents = list(filter(lambda x: x.flavor == VPC.flavor, self.parents))

                if len(vpc_parents) == 1:
                    vpc_parents[0].sync_state()
                    self.desired_state_definition["VpcId"] = vpc_parents[0]._vpc_id
                    return

        raise Exception("You need to specify either a VpcId or have a vpc as a parent")

    def _get_subnet_client(self):
        """
        Creates a new vpc_client

        Returns:
             vpc_client
        """
        return self.resource.Subnet(self._subnet_id)

    def _set_unique_keys(self):
        """
        Logic that sets keys from state definition that are used to uniquely identify the subnet

        """
        self.unique_keys = Subnet.UNIQUE_KEYS

    def get_status(self):
        """
        Calls boto3 describe_vpc using describe_subnets().

        Returns:
             status or {"status":"missing"}
        """
        subnets = self.client.describe_subnets(Filters=[{"Name":"tag:PCFName","Values":[self.subnet_name]}])
        if len(subnets["Subnets"]) == 1:
            return subnets["Subnets"][0]

    def _terminate(self):
        """
        Calls boto3 delete_subnet()

        Returns:
            boto3 delete_subnet() response
        """
        resp = self.client.delete_subnet(SubnetId=self.su)
        return resp

    def _start(self):
        """
        Creates subnet and adds tag for PCFName. The VpcId field or a parent vpc particle is required.

        Returns:
           boto3 create_subnet() response
        """
        self._set_vpc_id()
        resp = self.client.create_subnet(**pcf_util.param_filter(self.desired_state_definition,Subnet.START_PARAMS))
        self._subnet_id = resp['Subnet'].get("SubnetId")
        self.current_state_definition = resp
        tags = self.custom_config.get("Tags",[])
        tags.append({"Key":"PCFName","Value":self.subnet_name})
        self.subnet_client.create_tags(Tags=tags)
        return resp

    def _stop(self):
        """
        Calls _terminate()
        """
        return self._terminate()

    def _update(self):
        """
        No updates available
        """
        raise NotImplemented

    def sync_state(self):
        """
        Calls get_status() and updates the current_state_definition and the state.
        """
        full_status = self.get_status()
        if full_status is None:
            self.state = State.terminated
        else:
            self.state = Subnet.state_lookup.get(full_status["State"])
            self.current_state_definition = full_status
            self._subnet_id = full_status.get("SubnetId")

    def is_state_equivalent(self, state1, state2):
        """
        Args:
            state1 (State):
            state2 (State):

        Returns:
            bool
        """
        return Subnet.equivalent_states.get(state1) == Subnet.equivalent_states.get(state2)

    def is_state_definition_equivalent(self):
        """
        Since there is no update available for subnet this always returns True

        Returns:
             bool
        """
        return True

