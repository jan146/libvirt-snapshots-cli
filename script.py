
import sys
import os
import libvirt
from typing import TypeAlias
from enum import Enum

libvirtURI: str = "qemu:///system"
connType: TypeAlias = libvirt.virConnect
domainType: TypeAlias = libvirt.virDomain
snapshotType: TypeAlias = libvirt.virDomainSnapshot

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

def checkDomains(conn: connType):
	if len(getDomains(conn)) < 1:
		print("Error: no domains found", file=sys.stderr)

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
	for i, option in enumerate(options):
		print("\t[{:d}]: {:s}".format(i + 1, option))
	return inputInt(start=1, end=len(options))

def menuAction(conn: connType) -> Action:
	print()
	print("Select an action:")
	return Action(menu(list(action2str.values())))

def findRoot(snapshots: list[snapshotType]) -> snapshotType|None:
	children: set[libvirt.virDomainSnapshot] = set()
	for snapshot in snapshots:
		children.union(snapshot.listAllChildren())
	for snapshot in snapshots:
		if snapshot not in children:
			return snapshot
	return None

def executeAction(conn: connType, domain: domainType, action: Action):
	match action:
		case Action.LIST:
			snapshots: list[snapshotType] = domain.listAllSnapshots()
			root: snapshotType|None = findRoot(snapshots)
			print()
			print(" Current |    Name    |   Parent   ")
			print("---------+------------+------------")
			for snapshot in snapshots:
				current: str = "*" if snapshot.isCurrent() else " "
				name: str = snapshot.getName()
				parent: str = snapshot.getParent().getName() if snapshot is not root else "    -     "
				print("    {:1s}    | {:10s} | {:10s} ".format(current, name, parent))
		case Action.CREATE:
			pass
		case Action.REVERT:
			pass
		case Action.DELETE:
			pass
		case Action.EXIT:
			exit(0)

def menuDomain(conn: connType) -> domainType:
	domains: list[domainType] = getDomains(conn)
	print()
	print("Select a domain:")
	domainNames: list[str] = [domain.name() for domain in domains]
	domain: domainType = domains[menu(domainNames) - 1]
	return domain

def main():
	checkRoot()
	conn: connType = libvirt.open(libvirtURI)
	checkDomains(conn)
	domain: domainType = menuDomain(conn)
	action: Action = menuAction(conn)
	executeAction(conn, domain, action)
	conn.close()

main()
