#!/usr/bin/python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring, line-too-long

import argparse
import json
from os import path
from collections import Counter
import dns.resolver
from tld import get_fld
import idna
import sys

def to_punycode(domain, args, dns_resolver):
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
    dns_resolver.nameservers = ['8.8.8.8']
    ns_ips = []

    punycode_domain = to_punycode(domain, args, dns_resolver)

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

def main():
    dns_resolver = dns.resolver.Resolver()
    dns_resolver.raise_on_no_answer = True  # Prevent following CNAME records

    # Argument parsing
    arg_parser = argparse.ArgumentParser(description='Get DNS Information for domainname')
    arg_parser.add_argument('-d', '--domain', default=None, help='the domainname you want to inspect')
    arg_parser.add_argument('-n', '--nofile', default=False, action='store_true', help='do not write result to data/domain.json')
    arg_parser.add_argument('-q', '--quiet', default=False, action='store_true', help='do not print errors/warnings')
    args = arg_parser.parse_args()

    if args.domain is None:
        print("Please provide a domain using -d or --domain option.")
        return
    else:
        punycode_domain = to_punycode(args.domain, args, dns_resolver)

    own_resolver_found, ns_ips = resolve_dns(punycode_domain, args, dns_resolver)

    if not own_resolver_found and not args.quiet:
        print("# No NS found for " + args.domain)

    # gather dns-data
    entries = ['A', 'AAAA', 'CAA', 'CNAME', 'MX', 'SRV', 'PTR', 'SOA', 'TXT', 'NS']
    answers = {}

    for entry in entries:
        try:
            answer = dns_resolver.resolve(punycode_domain, entry)
            answers[entry] = [str(data) for data in answer]
        except dns.resolver.NoAnswer:
            continue
        except dns.resolver.NXDOMAIN:
            falling_back = True
            if not args.quiet:
                print("# No resolving answer from " + ns_ips[0])
            while len(ns_ips) > 1 and falling_back == True:
                removed_ns = ns_ips.pop(0)
                if not args.quiet:
                    print("# Removed non-answering " + removed_ns + " from list and fallback to "+ str(ns_ips))
                try:
                    answer = dns_resolver.resolve(punycode_domain, entry)
                    answers[entry] = [str(data) for data in answer]
                    falling_back == False
                except dns.resolver.NXDOMAIN:
                        continue

    if punycode_domain == get_fld(punycode_domain, fix_protocol=True):
        subdomain_prefix = '@'

        # gather dmarc-cnames (on tlds)
        try:
            dmarc_answer = dns_resolver.resolve('_dmarc.' + punycode_domain, 'CNAME')
            answers['~dmarc-cnames'] = [str(data) for data in dmarc_answer]
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            if not args.quiet:
                print('# no dmarc-cname-info for ' + args.domain + ' found.')

        # gather dmarc-cnames (on tlds)
        try:
            dmarc_answer = dns_resolver.resolve('_dmarc.' + punycode_domain, 'TXT')
            answers['~dmarc-txts'] = [str(data) for data in dmarc_answer]
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            if not args.quiet:
                print('# no dmarc-txt-info for ' + args.domain + ' found.')
    else:
        subdomain_prefix = punycode_domain.replace('.' + get_fld(punycode_domain, fix_protocol=True), '') 
    
    print('# subdomainprefix: ' + subdomain_prefix)

    prefixed_answers = {subdomain_prefix: answers}

    json_data = json.dumps(prefixed_answers, indent=4, sort_keys=True)
    print(json_data)

    # write data to file except file exists and data is still the same
    if not args.nofile:
        json_file_path = "data/" + punycode_domain + ".json"
        data_changed = False

        if path.isfile(json_file_path):
            with open(json_file_path, 'r') as myfile:
                old_json = json.loads(myfile.read())
                for entry in list(set(entries) | set(answers.keys())):
                    old_data = old_json.get(entry)
                    new_data = answers.get(entry)
                    if Counter(new_data) != Counter(old_data):
                        if not args.quiet:
                            print('Data Difference occurred!')
                        data_changed = True
                        continue
        else:
            data_changed = True

        if data_changed:
            with open(json_file_path, "w") as json_file:
                json_file.write(json_data)

if __name__ == "__main__":
    main()
