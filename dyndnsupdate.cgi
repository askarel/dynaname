#!/usr/bin/perl -w
# Copyright 2015 Bernhard M. Wiedemann
# Licensed under GPL v3 or later (see LICENSE file)
#
# use in FritzBox as custom Dynamic DNS provider with
# https://yourserver.domain/dyndnsupdate.cgi?hostname=<domain>&myip=<ipaddr>&dnsserver=<username>&key=URLENCODEDKxxx.keyFILE

use strict;
use CGI ':standard';
use POSIX 'strftime';
use File::Temp ':mktemp';

my $debug=0;
my $ttl=300;

print header(),start_html(-title=>"dynamic DNS updater"),
    start_form(-method=>"get"),
    textfield(-name=>'hostname'), " hostname to update", br,
    textfield(-name=>'myip'), " IP (optional)", br,
    textfield(-name=>'dnsserver'), " DNS server hosting the zone to update", br,
    textarea(-name=>'key', -rows=>5, -cols=>30), " Kxxx.key file content", br,
    submit(), br,
    end_form();

if(param()) {
    my %options;
    for my $p (qw(hostname myip dnsserver key)) {
        $options{$p}=param($p);
    }
    if(!$options{myip}) {
        # use sender's addr
        $options{myip}=$ENV{HTTP_X_FORWARDED_FOR} || $ENV{REMOTE_ADDR};
        $options{myip}=~s/^::ffff://
    }
    $options{myip}=lc($options{myip});
    $options{myip}=~s/[^0-9a-f.:]//g; # sanitize
    foreach my $p (qw(dnsserver hostname)) {
        $options{$p}=~s/[^0-9a-z.-]//g; # sanitize
    }
    (my $zone=$options{hostname})=~s/^[0-9a-z-]+\.//;
    my $rr="A"; # assume IPv4 by default
    if($options{myip}=~/:/) {
        $rr="AAAA";
    }
    my $time=POSIX::strftime('%F %H:%M:%S UTC', gmtime);
    my $request =
        "server $options{dnsserver}\n".
        "zone $zone\n".
        "update delete $options{hostname} $rr\n".
        "update add $options{hostname} $ttl $rr $options{myip}\n".
        "update delete $options{hostname} TXT\n".
        "update add $options{hostname} $ttl TXT \"Last update: $time\"\n".
        "send\nquit\n";
    if($debug) {
        open(DEBUG, ">", "/tmp/dyndns.log");
        print DEBUG join("\n", map {"$_=$ENV{$_}"} sort keys %ENV);
        if($ENV{REQUEST_METHOD} eq "POST") { print DEBUG <>}
        print DEBUG $request;
        close DEBUG;
    }
    umask(077);
    my ($tmpfile, $tmpfilename)=mkstemps("/tmp/dyndns.XXXXXX", ".key");
    print $tmpfile $options{key};
    close $tmpfile;
    (my $tmpfilename2=$tmpfilename)=~s/\.key/.private/;
    open($tmpfile, ">", $tmpfilename2) or die $!;
    my @key=split(" ",$options{key});
    print $tmpfile
        "Private-key-format: v1.3\n".
        "Algorithm: $key[5]\n".
        "Key: $key[6]$key[7]\n".
        "Bits: AAA=\n";
    close $tmpfile;
    print "Updating...\n",br;
    open(my $pipe, "| nsupdate -k $tmpfilename") or die $!;
    print $pipe $request;
    close $pipe;
    if($?>>8) {
        print "An error occurred. code ",$?>>8;
    } else {
        print "Updated successfully.";
    }
    unlink $tmpfilename, $tmpfilename2;
}

print end_html;
