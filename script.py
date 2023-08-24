
import sys
import os
import libvirt
from typing import TypeAlias

libvirtURI: str = "qemu:///system"
connType: TypeAlias = libvirt.virConnect

def checkRoot():
	if os.geteuid() != 0:
		print("Warning: non-root user might not have access to the libvirt API", file=sys.stderr)

def main():
	checkRoot()
	conn: connType = libvirt.open(libvirtURI)
	conn.close()

main()
