import requests
import argparse
from ihr.hegemony import Hegemony
from collections import defaultdict
import arrow
from matplotlib import pylab as plt
from iso3166 import countries


def get_pop_estimate(cc, min_population):
    url = 'http://v6data.data.labs.apnic.net/ipv6-measurement/Economies/{cc}/{cc}.asns.json'.format(cc=cc)

    params = dict(
        m=min_population
    )

    resp = requests.get(url=url, params=params)
    pop_est = resp.json() # Check the JSON Response Content documentation below

    return {x['as']:x for x in pop_est}


def compute_hegemony(pop_est, args, date):
    hege = Hegemony(originasns=pop_est.keys(), 
            start=date, end=date.shift(minutes=1))
    results = defaultdict(float)
    originasn_found = set()

    for hege_all_asn in hege.get_results():
        for hege in hege_all_asn:

            w = hege['hege']
            asn = hege['asn']
            originasn = hege['originasn']
            originasn_found.add(hege['originasn'])

            # don't count originasn (eyeball network)
            if args.remove_eyeball and asn==originasn:
                continue

            if not args.noweight:
                w  *= pop_est[originasn]['percent']

            results[asn] += w

    weight_sum = 0
    if args.noweight:
        weight_sum = len(originasn_found)
    else:
        weight_sum = sum([pop_est[oasn]['percent'] for oasn in originasn_found])

    results = {asn:w/weight_sum for asn, w in results.items()}
    return sorted(results.items(), key=lambda kv: kv[1])

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('country_code', type=str,
                        help='Country code')
    parser.add_argument('-r', '--remove_eyeball', action='count',
                        help="don't count origin ASes in hegemony calculation. \
Provides only results for transit networks.")
    parser.add_argument('-n', '--noweight', action='count',
                        help="don't weight by eyeball population")
    parser.add_argument('-t', '--top', type=int, default=10,
                        help="print top ASN")
    parser.add_argument('-m', '--min_population', type=float, default=0.01,
                        help="print top ASN")
    parser.add_argument('-s', '--start', type=str, 
                        help='Fetch data for the given start date')
    parser.add_argument('-e', '--end', type=str, 
                        help='Fetch data until the given end date. You should \
specify a start date to use that option.')
    parser.add_argument('-p', '--plot', type=str, 
                        help='Plot results in the given file')
    args = parser.parse_args()

    # set up the start and end dates
    date_start = None
    date_end = None
    if args.start is None:
        # Get recent results
        date_start = arrow.utcnow().shift(days=-2)
        date_end = date_start
    else:
        date_start = arrow.get(args.start)
        if args.end is None:
            date_end = date_start
        else:
            date_end = arrow.get(args.end)

    # set times to midnight
    date_start = date_start.replace(minute=0, hour=0, second=0, microsecond=0)
    date_end = date_end.replace(minute=0, hour=0, second=0, microsecond=0)

    pop_est = get_pop_estimate(args.country_code, args.min_population)
    print('# Found {} eyeball networks in {}'.format(
        len(pop_est), args.country_code)
        )
    
    # Find a good range of dates
    plot_data = defaultdict(lambda: defaultdict(list))
    granularity = None
    span = date_end - date_start
    if span.days <= 31:
        granularity = 'day'
    elif span.days <= 356:
        granularity = 'month'
    else:
        granularity = 'year'
    
    for date in arrow.Arrow.range(granularity, date_start, date_end):
        sorted_results = compute_hegemony(pop_est, args, date)

        print("# Results for {}".format(date))
        for i in range(1, min(len(sorted_results), args.top+1)):
            asn, val = sorted_results[len(sorted_results)-i]
            label = '-'
            if asn in pop_est:
                label = '+'

            print('{}, {}, {}'.format(asn, val, label))

            # keep data for plotting
            if args.plot:
                plot_data[asn]['time'].append(date.datetime)
                plot_data[asn]['hege'].append(val)

    # Plot the results if needed
    if args.plot:
        print(plot_data)
        fig = plt.figure(figsize=(8, 3))
        for asn, data in plot_data.items():
            plt.plot(data['time'], data['hege'], label='AS{}'.format(asn))
            plt.title('AS dependency of {}'.format(
                countries.get(args.country_code).name))

        plt.ylim([0, 1.05])
        plt.legend()
        fig.autofmt_xdate()
        plt.tight_layout()
        plt.savefig(args.plot)
