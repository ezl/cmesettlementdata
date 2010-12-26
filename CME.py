import urllib2
import re
import datetime

month_key = dict(JAN='1',
                 FEB='2',
                 MAR='3',
                 APR='4',
                 MAY='5',
                 JUN='6',
                 JLY='7',
                 AUG='8',
                 SEP='9',
                 OCT='10',
                 NOV='11',
                 DEC='12',)

expiration_pattern = re.compile(r"(JAN|FEB|MAR|APR|MAY|JUN|JLY|AUG|SEP|OCT|NOV|DEC)(\d{2})")
numeric_pattern = re.compile(r"-?\d+") # some strikes are apparently negative...
total_pattern = re.compile(r"TOTAL")

def retrieve_CME_settlement_data():
    url = "ftp://ftp.cmegroup.com/pub/settle/stlags"
    request = urllib2.Request(url)
    print "Grabbing CME Ag settlement data..."
    response = urllib2.urlopen(request)
    page = response.read()
    rows = page.split("\n")
    return rows

def get_published_settlement_time(row):
    """Parse timestamp from row 0"""
    settlement_time = re.compile(r"(\d{2}/\d{2}/\d{2} \d{2}:\d{2} \w{2})")
    # 12/15/10 06:00 PM
    m = re.search(settlement_time, row)
    if m:
        return m.group(0)
        # return datetime.datetime.strptime(m.group(0), "%m/%d/%y %I:%M %p")

def extract_expiration(row):
    m = re.search(expiration_pattern, row)
    if m:
        month, year = month_key[m.group(1)], m.group(2)
        return month, year
    else:
        return "Nan"

def extract_strike(row):
    m = re.match(numeric_pattern, row)
    if m:
        return m.group(0)
    else:
        return "Nan"

def get_headers(header_row):
    """Return headers for contract data.

       Headers are the 3rd row in the FTP file.
       'MTH/                 ---- DAILY ---                        PT                     -------  PRIOR  DAY  -------',
       'STRIKE     OPEN      HIGH      LOW       LAST      SETT    CHGE     EST.VOL       SETT         VOL         INT',

       Use our own more descriptive labels instead of row.split()
    """
    # headers = ["STRIKE", "OPEN", "HIGH", "LOW", "LAST", "SETT", "CHG", "EST.VOL", "PRIOR_SETT", "PRIOR_VOL", "PRIOR INT"]
    headers = header_row.split()
    return headers

def get_column_markers(header_row):
    """Return the column index for the last column of each header."""

    marked = re.sub("\w(?= |$)", "*", header_row) # match end of word or line
    end_markers = [i for i in range(len(marked)) if marked[i] is "*"]
    end_markers[0] = 0 # garbage hack -- all the columns except the first are right
                       # justified.  set the first one to 0 (always exist for data
                       # columns anyways)
    return end_markers

def is_data_row(row):
    """Determine if a row from the text file contains contract data.

       Test looks to see if it the row starts with a numeric or month (option or fut) word.
       If so, its a contract of some sort, otherwise, its a section header."""

    if re.match(expiration_pattern, row) or re.match(numeric_pattern, row):
        return True
    else:
        return False

def get_row_type(row):
    """Determine what type of data a row contains.

       Rows come in 4 types:
           1. Future -- start with a month name (matches expiration_pattern)
           2. Option -- start with a strike (matches numeric_pattern)
           3. Aggregate -- start with the word "TOTAL"
           4. New section heading -- starts with a product name

       Return the type as a string:
           1. "FUT"
           2. "OPT"
           3. "TOTAL"
           4. "HEADER"
        """

    if re.match(expiration_pattern, row):
        return "FUT"
    elif re.match(numeric_pattern, row):
        return "OPT"
    elif re.match(total_pattern, row):
        return "TOTAL"
    else:
        return "HEADER"

if __name__ == "__main__":
    # Settings
    products = None # list of products to get. None for all.

    rows = retrieve_CME_settlement_data()
    date_row = rows[0]
    header_row = rows[2]
    data = rows[3:-2] # exclude the last row

    settlement_time = get_published_settlement_time(date_row)
    headers = get_headers(header_row)
    column_markers = get_column_markers(header_row)

    row_length = max(len(row) for row in data)

    for row in data:
        row_type = get_row_type(row)
        if row_type == "HEADER":
            product = row
            symbol = product # TODO: wrong.
            if True:
                print product
        elif row_type == "FUT" or row_type == "OPT":
            # space fill short rows
            row = row.ljust(row_length)
            # place a marker if a column is blank
            row = "".join(["0" if row[i] == " " and i in column_markers else row[i] \
                           for i in range(len(row))
                          ]) # I hate myself.  I know there's a better way but
                             # I don't know what it is.

            # F it. Hacky but effective.
            px_open, px_high, px_low, px_last, px_settle = row.split()[1:6]
            est_vol, prior_settle, prior_vol, prior_open_interest = row.split()[7:]
            exp_day = "0" # apparently only daily options have exp days in CME datamine. All others are 0.

            # Process this row
            # http://www.cmegroup.com/market-data/datamine-historical-data/files/EODLayoutGuideCSV.pdf
            # http://www.cmegroup.com/market-data/datamine-historical-data/endofday.html
            if row_type == "FUT":
                exp_month, exp_year = extract_expiration(row) # fut expiration data is stored on each row
                strike = "0"
            elif row_type == "OPT":
                exp_month, exp_year = extract_expiration(product) # opt expiration data is stored in the section heading
                strike = extract_strike(row)

            if "PUT" in product:
                fut_opt_indicator = "P"
            elif "CALL" in product:
                fut_opt_indicator = "C"
            else:
                # for now, assume its a fut.
                # TODO: Is this a bad assumption?
                # What are SWP, SWAP, "FUT", "FUTURE", "Future", "Futures".
                # RATE, SSF, and other unlabeled contract types (e.g. BUTTER)
                fut_opt_indicator = "F"

# required format is [trade_date, symbol, fut_opt_indicator, exp_month, exp_day, exp_year, strike, open, high, low, close, settle, volume, open_interest]

            formatted_row = [settlement_time,
                             symbol,
                             fut_opt_indicator,
                             exp_month,
                             exp_day,
                             exp_year,
                             strike,
                             px_open,
                             px_high,
                             px_low,
                             px_last,
                             px_settle,
                             est_vol,
                             prior_settle,
                             prior_vol,
                             prior_open_interest,
                             ]

            print ",".join(formatted_row)

