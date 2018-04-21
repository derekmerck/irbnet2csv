# irbnet2csv

Scrape IRB info and protocol documents out of IRBNet.org
and reformat info into a spreadsheet.

## Dependencies

- [Selenium](http://selenium-python.readthedocs.io) and
  [chromedriver](https://sites.google.com/a/chromium.org/chromedriver/downloads)
- [Beautiful Soup](https://beautiful-soup-4.readthedocs.io)
- [dateutil](https://dateutil.readthedocs.io)
- [unicodecsv-python](https://github.com/jdunck/python-unicodecsv)

## Usage

```bash
$ python irbnet2csv.py -u user -p pwd -o "proj.csv" -d
```

