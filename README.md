# Blogspot Crawler

A simple crawler using Beautiful Soup 4 and requests to obtain every post
in a Blogger/Blogspot website, via clicking on next page.

It only downloads the post body in html format, but creating a Jekyll file
with the title and tags. As a result, the entire blog dump is very small.

In the future, it will download images and jekyllify the HTML output.

## Usage
Just put the url and a destination folder. Posts should be downloaded as the url without the basename.

```
usage: ./blogspotCrawler.py [-h] [-o DESTINATION] url

Blogspot crawler

positional arguments:
  url                   Blog url

optional arguments:
  -h, --help            show this help message and exit
  -o DESTINATION, --output DESTINATION
                        Output folder
```

## Ideas for the future
- [ ] Quietly process ReadTimeout exceptions on future callback
- [ ] Auto download images
- [ ] Jekyllify output
- [ ] Add wordpress support

-----------------
This program is licensed under an MIT License

(C) 2021 [David Davó](https://ddavo.me/en)