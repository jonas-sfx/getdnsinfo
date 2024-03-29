#!/usr/bin/python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring, line-too-long

import argparse
import json
import sys
from collections import Counter
from os import path

import dns.resolver
from tld import get_fld
import idna

DEFAULT_NAMESERVER = '8.8.8.8'
DNS_ENTRIES = ['A', 'AAAA', 'CAA', 'CNAME', 'MX', 'SRV', 'PTR', 'SOA', 'TXT', 'NS']

def to_punycode(domain, args):
    # Split the domain name into labels
    labels = domain.split('.')
    punycode_labels = []

    try:
        # Encode each label to punycode
        for label in labels:
            # Check if the label contains underscores
            if '_' in label:
                # For labels with underscores, keep them as they are
                punycode_label = label
            else:
                # For labels without underscores, encode using IDNA
                punycode_label = idna.encode(label).decode('ascii')

            punycode_labels.append(punycode_label)

        # Join the punycode labels back together
        punycode_domain = '.'.join(punycode_labels)

    except UnicodeError:
        print("Error: Unable to convert domain to Punycode.")
        sys.exit()
        return None

    if not args.quiet and punycode_domain != args.domain:
        print('# punycode-converted: ' + args.domain + ' to ' + punycode_domain)
    return punycode_domain


def resolve_dns(domain, args, dns_resolver):
    dns_resolver.nameservers = [DEFAULT_NAMESERVER]
    ns_ips = []

    punycode_domain = to_punycode(domain, args)

    try:
        my_target_ns = dns_resolver.resolve(punycode_domain, 'NS')
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        my_target_ns = []
        if not args.quiet:
            print('# No Direct NS found!')

    try:
        tld_target_ns = dns_resolver.resolve(get_fld(punycode_domain, fix_protocol=True), 'NS')
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        tld_target_ns = []
        if not args.quiet:
            print('# No NS for TLD found!')

    target_ns = list(set(my_target_ns).union(set(tld_target_ns)))

    if not target_ns:
        return False, None

    for ns in target_ns:
        ns_a = dns_resolver.resolve(str(ns).strip('.'), 'A')
        ns_ips.extend(str(data) for data in ns_a)

    dns_resolver.nameservers = ns_ips
    if not args.quiet:
        print('# NS found:' + str(ns_ips))
    return True, ns_ips

def gather_dns_data(domain, dns_resolver, ns_ips, args):
    answers = {}

    for entry in DNS_ENTRIES:
        try:
            answer = dns_resolver.resolve(domain, entry)
            answers[entry] = [str(data) for data in answer]
        except dns.resolver.NoAnswer:
            continue
        except dns.resolver.NXDOMAIN:
            fallback_nonanswers = True
            if not args.quiet:
                print("# No resolving answer from " + ns_ips[0])
            while len(ns_ips) > 1 and fallback_nonanswers is True:
                removed_ns = ns_ips.pop(0)
                if not args.quiet:
                    print("# Removed non-answering " + removed_ns + " from list and fallback to "+ str(ns_ips))
                try:
                    answer = dns_resolver.resolve(domain, entry)
                    answers[entry] = [str(data) for data in answer]
                    fallback_nonanswers == False
                except dns.resolver.NXDOMAIN:
                    continue

    while len(answers.keys())== 0:
        removed_ns = ns_ips.pop(0)
        if not args.quiet:
            print("# Removed non/empty-answering " + removed_ns + " from list and fallback to "+ str(ns_ips))
        try:
            answer = dns_resolver.resolve(domain, entry)
            answers[entry] = [str(data) for data in answer]
        except dns.resolver.NoAnswer:
            continue

    return answers

def create_prefixed_answers(punycode_domain, answers, dns_resolver, args):
    prefixed_answers = {}
    if punycode_domain == get_fld(punycode_domain, fix_protocol=True):
        subdomain_prefix = '@'

        # gather dmarc-cnames (on tlds)
        try:
            dmarc_answer = dns_resolver.resolve('_dmarc.' + punycode_domain, 'CNAME')
            prefixed_answers['_dmarc'] = {'CNAME': [str(data) for data in dmarc_answer]}
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            if not args.quiet:
                print('# no dmarc-cname-info for ' + args.domain + ' found.')

        # gather dmarc-txts (on tlds)
        try:
            dmarc_answer = dns_resolver.resolve('_dmarc.' + punycode_domain, 'TXT')
            prefixed_answers.setdefault('_dmarc', {})['TXT'] = [str(data) for data in dmarc_answer]
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            if not args.quiet:
                print('# no dmarc-txt-info for ' + args.domain + ' found.')

    else:
        subdomain_prefix = punycode_domain.replace('.' + get_fld(punycode_domain, fix_protocol=True), '')

    if not args.quiet:
        print('# subdomainprefix: ' + subdomain_prefix)
    prefixed_answers[subdomain_prefix] = answers
    
    return prefixed_answers

def write_to_file(prefixed_answers, punycode_domain, args):
    if not args.nofile:
        json_file_path = "data/" + punycode_domain + ".json"
        data_changed = False

        if path.isfile(json_file_path):
            with open(file=json_file_path, mode='r', encoding="utf-8") as myfile:
                old_json = json.loads(myfile.read())
                for entry in list(set(DNS_ENTRIES) | set(prefixed_answers.keys())):
                    old_data = old_json.get(entry)
                    new_data = prefixed_answers.get(entry)
                    if Counter(new_data) != Counter(old_data):
                        if not args.quiet:
                            print('Data Difference occurred!')
                        data_changed = True
                        continue
        else:
            data_changed = True

        if data_changed:
            with open(file=json_file_path, mode='w', encoding="utf-8") as json_file:
                json_file.write(json.dumps(prefixed_answers, indent=4, sort_keys=True))

def parse_arguments():
    arg_parser = argparse.ArgumentParser(description='Get DNS Information for domainname')
    arg_parser.add_argument('-d', '--domain', default=None, help='the domainname you want to inspect')
    arg_parser.add_argument('-n', '--nofile', default=False, action='store_true', help='do not write result to data/domain.json')
    arg_parser.add_argument('-q', '--quiet', default=False, action='store_true', help='do not print errors/warnings')
    return arg_parser.parse_args()

def main():
    dns_resolver = dns.resolver.Resolver()
    dns_resolver.raise_on_no_answer = True  # Prevent following CNAME records

    args = parse_arguments()

    if args.domain is None:
        print("Please provide a domain using -d or --domain option.")
        return

    punycode_domain = to_punycode(args.domain, args)

    own_resolver_found, ns_ips = resolve_dns(punycode_domain, args, dns_resolver)

    if not own_resolver_found and not args.quiet:
        print("# No NS found for " + args.domain)

    answers = gather_dns_data(punycode_domain, dns_resolver, ns_ips, args)
    prefixed_answers = create_prefixed_answers(punycode_domain, answers, dns_resolver, args)

    print(json.dumps(prefixed_answers, indent=4, sort_keys=True))
    write_to_file(prefixed_answers, punycode_domain, args)

if __name__ == "__main__":
    main()
