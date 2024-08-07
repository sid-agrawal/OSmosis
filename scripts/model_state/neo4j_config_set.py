import argparse
import configparser

parser = argparse.ArgumentParser("neo4j_config_set")
parser.add_argument("--url", help="connection URL of neo4j instance WITH the protocol")
parser.add_argument("--user", help="username of neo4j instance")
parser.add_argument("--password", help="password of neo4j instance")
args = parser.parse_args()

config = configparser.ConfigParser()

if __name__ == "__main__":
    config["neo4j"] = {"url": "", "user": "", "pass": ""}
    if args.user is None and args.password is None and args.url is None:
        parser.parse_args(["-h"])
        raise SystemExit()

    if args.user is not None and len(args.user) > 0:
        config["neo4j"]["user"] = args.user

    if args.password is not None and len(args.password) > 0:
        config["neo4j"]["pass"] = args.password

    if args.url is not None and len(args.url) > 0:
        config["neo4j"]["url"] = args.url

    with open("config.txt", "w") as configfile:
        config.write(configfile)
