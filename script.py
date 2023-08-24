
import sys
import os
import libvirt
from typing import TypeAlias
from enum import Enum

libvirtURI: str = "qemu:///system"
connType: TypeAlias = libvirt.virConnect
domainType: TypeAlias = libvirt.virDomain

class Action(Enum):
	LIST	= 1
	CREATE	= 2
	REVERT	= 3
	DELETE	= 4
	EXIT	= 5

action2str: dict[Action, str] = {
	Action.LIST:	"List snapshots",
	Action.CREATE:	"Create snapshot",
	Action.REVERT:	"Revert snapshot",
	Action.DELETE:	"Delete snapshot",
	Action.EXIT:	"Exit",
}

def checkRoot():
	if os.geteuid() != 0:
		print("Warning: non-root user might not have access to the libvirt API", file=sys.stderr)

def getDomains(conn: connType) -> list[domainType]:
	return conn.listAllDomains(0)

def inputInt(start: int, end: int) -> int:
	while True:
		strInput: str = input("Enter number in range [{:d}-{:d}]: ".format(start, end))
		try:
			intInput: int = int(strInput)
			if start <= intInput <= end:
				return intInput
			else:
				print("Entered number is not in range", file=sys.stderr)
		except ValueError:
			print("Input is not an integer", file=sys.stderr)

def menu(options: list[str]) -> int:
	if len(options) < 2:
		return 0
	print()
	for i, option in enumerate(options):
		print("\t[{:d}]: {:s}".format(i + 1, option))
	return inputInt(start=1, end=len(options))

def menuMain(conn: connType) -> int:
	return menu(list(action2str.values()))

def executeAction(action: Action):
	match action:
		case Action.LIST:
			pass
		case Action.CREATE:
			pass
		case Action.REVERT:
			pass
		case Action.DELETE:
			pass
		case Action.EXIT:
			exit(0)

def main():
	checkRoot()
	conn: connType = libvirt.open(libvirtURI)
	action: Action = Action(menuMain(conn))
	executeAction(action)
	conn.close()

main()
