"""
Starting point of CSI driver GRP server
"""
import logging
import os
import time
import signal

from concurrent import futures

import grpc

import csi_pb2_grpc
from controllerserver import ControllerServer
from identityserver import IdentityServer
from kadalulib import CommandException, logf, logging_setup
from nodeserver import NodeServer
from volumeutils import (HOSTVOL_MOUNTDIR, get_pv_hosting_volumes,
                         mount_glusterfs, reload_glusterfs)

_ONE_DAY_IN_SECONDS = 60 * 60 * 24

def mount_storage():
    """
    Mount storage if any volumes exist after a pod reboot
    """
    if os.environ.get("CSI_ROLE", "-") != "provisioner":
        logging.debug("Volume need to be mounted on only provisioner pod")
        return

    host_volumes = get_pv_hosting_volumes({})
    for volume in host_volumes:
        if volume["kformat"] == "non-native":
            # Need to skip mounting external non-native mounts in-order for
            # kadalu-quotad not to set quota xattrs
            continue
        hvol = volume["name"]
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hvol)
        try:
            mount_glusterfs(volume, mntdir)
            logging.info(logf("Volume is mounted successfully", hvol=hvol))
        except CommandException:
            logging.error(logf("Unable to mount volume", hvol=hvol))
    return


def reconfigure_mounts(_signum, _frame):
    """
    Reconfigure the mounts by regenerating the volfiles.
    """
    host_volumes = get_pv_hosting_volumes({})
    for volume in host_volumes:
        if volume["type"] == "External":
            # Need to skip remount external
            continue
        if reload_glusterfs(volume):
            logging.info(logf("Volume reloaded successfully", volume=volume))

def main():
    """
    Register Controller Server, Node server and Identity Server and start
    the GRPC server in required endpoint
    """
    logging_setup()

    # If Provisioner pod reboots, mount volumes if they exist before reboot
    mount_storage()

    signal.signal(signal.SIGHUP, reconfigure_mounts)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    csi_pb2_grpc.add_ControllerServicer_to_server(ControllerServer(), server)
    csi_pb2_grpc.add_NodeServicer_to_server(NodeServer(), server)
    csi_pb2_grpc.add_IdentityServicer_to_server(IdentityServer(), server)

    server.add_insecure_port(os.environ.get("CSI_ENDPOINT", "unix://plugin/csi.sock"))
    logging.info("Server started")
    server.start()
    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == '__main__':
    main()
