# -*- coding: utf-8 -*-

import utils

from botocore.exceptions import ClientError
from sceptre.hooks import Hook
from exceptions import UndefinedExportException, UndefinedParameterException


class EC2Notify(Hook):
    """
    Hook for notifying about provisioned resources.

    :param argument: The Sender name and email
    :type argument: str

    """
    def __init__(self, *args, **kwargs):
        super(EC2Notify, self).__init__(*args, **kwargs)

    def run(self):
        """
        Notify resource owner of the provisioned EC2.
        """
        args = self.argument
        utils.validate_args(args)
        sender_name = args.split(' ')[0]
        sender_email = args.split(' ')[1]

        # Defaults parameters allows user to optionally specify them in scepter
        # Therefore we need to get parameter values from cloudformation
        connection_manager = self.stack.template.connection_manager
        try:
            response = connection_manager.call(
                service="cloudformation",
                command="describe_stacks",
                kwargs={"StackName": self.stack.external_name},
                profile=self.stack.profile,
                region=self.stack.region,
                stack_name=self.stack.name
            )
        except ClientError as e:
            raise e

        stack_parameters = response['Stacks'][0]['Parameters']
        stack_outputs = response['Stacks'][0]['Outputs']
        owner_email = utils.get_parameter_value(stack_parameters, 'OwnerEmail')

        # EC2 info is auto assigned and only available in CF outputs
        ec2_info ={}
        ec2_info['id'] = utils.get_output_value(
            stack_outputs,
            self.stack.region + '-' + self.stack.external_name + '-' + 'Ec2InstanceId')
        ec2_info['private_ip'] = utils.get_output_value(
            stack_outputs,
            self.stack.region + '-' + self.stack.external_name + '-' + 'Ec2InstancePrivateIp')

        # EC2 in private subnet will not have a pubilc IP
        try:
            ec2_info['public_ip'] = utils.get_output_value(
                stack_outputs,
                self.stack.region + '-' + self.stack.external_name + '-' + 'Ec2InstancePublicIp')
        except UndefinedExportException as e:
            pass

        self.logger.info("EC2 instance id: " +  ec2_info['id'])

        info = ''
        for k, v in ec2_info.items():
            info = info + k + ": " + v + "<br />"

        message = ("An EC2 instance has been provisioned on your behalf. "
                     "<br />" + info + "<br />")

        if 'public_ip' in ec2_info:
            message = message + ("<b> Resource Connection Info </b> <br />"
                                 "If you provisioned an EC2 instance: "
                                 "Open a terminal, then type ssh YOUR_JUMPCLOUD_USERNAME@IP_ADDRESS "
                                 "(i.e. ssh jsmith@" + ec2_info["public_ip"] + ") <br />"
                                 "If you provisioned a Windows EC2: "
                                 "Run a "
                                 "<a href=\"https://docs.microsoft.com/en-us/windows-server/remote/remote-desktop-services/clients/remote-desktop-clients\">RDP client</a> "
                                 "then connect to " + ec2_info["public_ip"] + " with your Jumpcloud credentials")
        else:
            message = message + ("<b> Resource Connection Info </b> <br />"
                                 "Login to the Sage VPN <br />"
                                 "If you provisioned an EC2 instance: "
                                 "Open a terminal, then type ssh YOUR_JUMPCLOUD_USERNAME@IP_ADDRESS "
                                 "(i.e. ssh jsmith@" + ec2_info["private_ip"] + ") <br />"
                                 "If you provisioned a Windows EC2: "
                                 "Run a "
                                 "<a href=\"https://docs.microsoft.com/en-us/windows-server/remote/remote-desktop-services/clients/remote-desktop-clients\">RDP client</a> "
                                 "then connect to " + ec2_info["private_ip"] + " with your Jumpcloud credentials")
        try:
            response = utils.email_owner(
                self.stack,
                sender_email,
                owner_email,
                sender_name + " Automated Provisioner",
                message)
        except ClientError as e:
            self.logger.error(e.response['Error']['Message'])
        else:
            self.logger.info("Email sent to " + owner_email)
            self.logger.info("Message ID: " + response['MessageId'])
