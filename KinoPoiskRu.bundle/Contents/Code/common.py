# -*- coding: utf-8 -*-
#
# Russian metadata plugin for Plex, which uses http://www.kinopoisk.ru/ to get the tag data.
# Плагин для обновления информации о фильмах использующий КиноПоиск (http://www.kinopoisk.ru/).
# Copyright (C) 2012 Zhenya Nyden
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.
#
# @author zhenya (Yevgeny Nyden)
# @revision 114

import string, sys, time, re

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_2) AppleWebKit/534.51.22 (KHTML, like Gecko) Version/5.1.1 Safari/534.51.22'
ENCODING_PLEX = 'utf-8'

SCORE_PENALTY_ITEM_ORDER = 2
SCORE_PENALTY_YEAR = 17
SCORE_PENALTY_TITLE = 40

IMAGE_CHOICE_ALL = 1
IMAGE_CHOICE_BEST = 2
IMAGE_CHOICE_NOTHING = 3
IMAGE_CHOICE_THUMB_ONLY = 4
IMAGE_SCORE_BEST_THRESHOLD = 50
IMAGE_SCORE_MAX_NUMBER_OF_ITEMS = 5
IMAGE_SCORE_ITEM_ORDER_BONUS_MAX = 25
IMAGE_SCORE_RESOLUTION_BONUS_MAX = 25
IMAGE_SCORE_RATIO_BONUS_MAX = 45
IMAGE_SCORE_THUMB_BONUS = 5
POSTER_SCORE_MIN_RESOLUTION_PX = 60 * 1000
POSTER_SCORE_MAX_RESOLUTION_PX = 600 * 1000
POSTER_SCORE_BEST_RATIO = 0.7
ART_SCORE_BEST_RATIO = 1.5
ART_SCORE_MIN_RESOLUTION_PX = 200 * 1000
ART_SCORE_MAX_RESOLUTION_PX = 1000 * 1000


class Thumbnail:
  """ Represents an image search result data.
  """
  def __init__(self, thumbImgUrl, fullImgUrl, fullImgWidth, fullImgHeight, index, score):
    self.thumbImgUrl = thumbImgUrl
    self.fullImgUrl = fullImgUrl
    self.fullImgWidth = fullImgWidth
    self.fullImgHeight = fullImgHeight
    self.index = index
    self.score = score

  def __repr__(self):
    return repr((self.thumbImgUrl, self.fullImgUrl, self.fullImgWidth, self.fullImgHeight, self.index, self.score))

def ThumbnailCmp(one, two):
  return one.score - two.score


class Preferences:
  """ These instance variables are populated from plugin preferences.
  """
  def __init__(self,
      (imageChoiceName, imageChoiceDefault),
      (maxPostersName, maxPostersDefault),
      (maxArtName, maxArtDefault),
      (getAllActorsName, getAllActorsDefault),
      (imdbSupportName, imdbSupportDefault),
      (cacheTimeName, cacheTimeDefault)):
    self.imageChoiceName = imageChoiceName
    self.imageChoice = imageChoiceDefault
    self.maxPostersName = maxPostersName
    self.maxPosters = maxPostersDefault
    self.maxArtName = maxArtName
    self.maxArt = maxArtDefault
    self.getAllActorsName = getAllActorsName
    self.getAllActors = getAllActorsDefault
    self.imdbSupportName = imdbSupportName
    self.imdbSupport = imdbSupportDefault
    self.cacheTimeName = cacheTimeName
    self.cacheTime = cacheTimeDefault
    self.cacheTimeDefault = cacheTimeDefault

  def readPluginPreferences(self):
    # Setting image (poster and funart) preferences.
    if self.imageChoiceName is not None:
      imageChoice = Prefs[self.imageChoiceName]
      if imageChoice == u'плохие не брать':
        self.imageChoice = IMAGE_CHOICE_BEST
      elif imageChoice == u'не брать никаких':
        self.imageChoice = IMAGE_CHOICE_NOTHING
      elif imageChoice == u'брать все':
        self.imageChoice = IMAGE_CHOICE_ALL
      elif imageChoice == u'только ярлык':
        self.imageChoice = IMAGE_CHOICE_THUMB_ONLY
      Log.Debug('PREF: Setting image preference to %d (%s).' % (self.imageChoice, imageChoice))

    if self.maxPostersName is not None:
      self.maxPosters = int(Prefs[self.maxPostersName])
      Log.Debug('PREF: Max poster results is set to %d.' % self.maxPosters)
    if self.maxArtName is not None:
      self.maxArt = int(Prefs[self.maxArtName])
      Log.Debug('PREF: Max art results is set to %d.' % self.maxArt)
    if self.getAllActorsName is not None:
      self.getAllActors = Prefs[self.getAllActorsName]
      Log.Debug('PREF: Parse all actors is set to %s.' % str(self.getAllActors))

    # Setting IMDB support.
    if self.imdbSupportName is not None:
      self.imdbSupport = Prefs[self.imdbSupportName]
      Log.Debug('PREF: IMDB support is set to %s.' % str(self.imdbSupport))

    # Setting cache expiration time.
    if self.cacheTimeName is not None:
      self.cacheTime = parseAndSetCacheTimeFromPrefs(self.cacheTimeName, self.cacheTimeDefault)


def parseAndSetCacheTimeFromPrefs(cacheTimeName, cacheTimeDefault):
  """ Reads cache time preferences and returns it's value as an int.
  """
  prefCache = Prefs[cacheTimeName]
  if prefCache == u'1 день':
    cacheTime = CACHE_1DAY
  elif prefCache == u'1 неделя':
    cacheTime = CACHE_1DAY
  elif prefCache == u'1 месяц':
    cacheTime = CACHE_1MONTH
  elif prefCache == u'1 год':
    cacheTime = CACHE_1MONTH * 12
  else:
    cacheTime = cacheTimeDefault
  HTTP.CacheTime = cacheTime
  Log.Debug('PREF: Setting cache expiration to %d seconds (%s).' % (cacheTime, prefCache))
  return cacheTime


def getElementFromHttpRequest(url, encoding):
  """ Fetches a given URL and returns it as an element.
      Функция преобразования html-кода в xml-код.
  """
  for i in range(3):
    errorCount = 0
    try:
      response = HTTP.Request(url, headers = {'User-agent': USER_AGENT, 'Accept': 'text/html'})
      return HTML.ElementFromString(str(response).decode(encoding))
    except:
      errorCount += 1
      Log.Debug('Error fetching URL: "%s".' % url)
      time.sleep(1 + errorCount)
  return None


def getResponseFromHttpRequest(url):
  """ Requests an image given its URL and returns a request object.
  """
  try:
    response = HTTP.Request(url, headers = {'User-agent': USER_AGENT, 'Accept': 'image/jpeg'})
    return response
  except:
    Log.Debug('Error fetching URL: "%s".' % url)
  return None


def printSearchResults(results):
  """ Sends a list of media results to debug log.
  """
  Log.Debug('Search produced %d results:' % len(results))
  index = 0
  for result in results:
    Log.Debug(' ... %d: id="%s", name="%s", year="%s", score="%d".' %
              (index, result.id, result.name, str(result.year), result.score))
    index += 1


def printImageSearchResults(thumbnailList):
  Log.Debug('printing %d image results:' % len(thumbnailList))
  index = 0
  for result in thumbnailList:
    Log.Debug(' ... %d: index=%s, score=%s, URL="%s".' %
              (index, result.index, result.score, result.fullImgUrl))
    index += 1
  return None


def logException(msg):
  excInfo = sys.exc_info()
  Log.Exception('%s; exception: %s; cause: %s' % (msg, excInfo[0], excInfo[1]))


def scoreMediaTitleMatch(mediaName, mediaYear, title, altTitle, year, itemIndex):
  """ Compares page and media titles taking into consideration
      media item's year and title values. Returns score [0, 100].
      Search item scores 100 when:
        - it's first on the list of results; AND
        - it equals to the media title (ignoring case) OR all media title words are found in the search item; AND
        - search item year equals to media year.

      For now, our title scoring is pretty simple - we check if individual words
      from media item's title are found in the title from search results.
      We should also take into consideration order of words, so that "One Two" would not
      have the same score as "Two One". Also, taking into consideration year difference.
  """
  Log.Debug('comparing "%s"-%s with "%s"-%s (%s)...' % (str(mediaName), str(mediaYear), str(title), str(year), str(altTitle)))
  # Max score is when both title and year match exactly.
  score = 100

  # Item order penalty (the lower it is on the list or results, the larger the penalty).
  score = score - (itemIndex * SCORE_PENALTY_ITEM_ORDER)

  # Compute year penalty: [equal, diff>=3] --> [0, MAX].
  yearPenalty = SCORE_PENALTY_YEAR
  mediaYear = toInteger(mediaYear)
  year = toInteger(year)
  if mediaYear is not None and year is not None:
    yearDiff = abs(mediaYear - year)
    if not yearDiff:
      yearPenalty = 0
    elif yearDiff == 1:
      yearPenalty = int(SCORE_PENALTY_YEAR / 3)
    elif yearDiff == 2:
      yearPenalty = int(SCORE_PENALTY_YEAR / 2)
  else:
    # If year is unknown, don't penalize the score too much.
    yearPenalty = int(SCORE_PENALTY_YEAR / 3)
  score = score - yearPenalty

  # Compute title penalty.
  titlePenalty = computeTitlePenalty(mediaName, title)
  altTitlePenalty = 100
  if altTitle is not None:
    altTitlePenalty = computeTitlePenalty(mediaName, altTitle)
  titlePenalty = min(titlePenalty, altTitlePenalty)
  score = score - titlePenalty

  # IMPORTANT: always return an int.
  score = int(score)
  Log.Debug('***** title scored %d' % score)
  return score


def scoreThumbnailResult(thumb, isPoster):
  """ Given a Thumbnail object that represents an poster or a funart result,
      scores it, and stores the score on the passed object (thumb.score).
  """
  Log.Debug('-------Scoring image %sx%s with index %d:\nfull image URL: "%s"\nthumb image URL: %s' %
                    (str(thumb.fullImgWidth), str(thumb.fullImgHeight), thumb.index, str(thumb.fullImgUrl), str(thumb.thumbImgUrl)))
  score = 0
  if thumb.fullImgUrl is None:
    thumb.score = 0
    return

  if thumb.index < IMAGE_SCORE_MAX_NUMBER_OF_ITEMS:
    # Score bonus from index for items below 10 on the list.
    bonus = IMAGE_SCORE_ITEM_ORDER_BONUS_MAX * \
        ((IMAGE_SCORE_MAX_NUMBER_OF_ITEMS - thumb.index) / float(IMAGE_SCORE_MAX_NUMBER_OF_ITEMS))
    Log.Debug('++++ adding order bonus: +%s' % str(bonus))
    score += bonus

  if thumb.fullImgWidth is not None and thumb.fullImgHeight is not None:
    # Get a resolution bonus if width*height is more than a certain min value.
    if isPoster:
      minPx = POSTER_SCORE_MIN_RESOLUTION_PX
      maxPx = POSTER_SCORE_MAX_RESOLUTION_PX
      bestRatio = POSTER_SCORE_BEST_RATIO
    else:
      minPx = ART_SCORE_MIN_RESOLUTION_PX
      maxPx = ART_SCORE_MAX_RESOLUTION_PX
      bestRatio = ART_SCORE_BEST_RATIO
    pixelsCount = thumb.fullImgWidth * thumb.fullImgHeight
    if pixelsCount > minPx:
      if pixelsCount > maxPx:
        pixelsCount = maxPx
      bonus = float(IMAGE_SCORE_RESOLUTION_BONUS_MAX) * \
          float((pixelsCount - minPx)) / float((maxPx - minPx))
      Log.Debug('++++ adding resolution bonus: +%s' % str(bonus))
      score += bonus
    else:
      Log.Debug('++++ no resolution bonus for %dx%d' % (thumb.fullImgWidth, thumb.fullImgHeight))

    # Get an orientation (Portrait vs Landscape) bonus. (we prefer images that are have portrait orientation.
    ratio = thumb.fullImgWidth / float(thumb.fullImgHeight)
    ratioDiff = math.fabs(bestRatio - ratio)
    if ratioDiff < 0.5:
      bonus = IMAGE_SCORE_RATIO_BONUS_MAX * (0.5 - ratioDiff) * 2.0
      Log.Debug('++++ adding "%s" ratio bonus: +%s' % (str(ratio), str(bonus)))
      score += bonus
    else:
      # Ignoring Landscape ratios.
      Log.Debug('++++ no ratio bonus for %dx%d' % (thumb.fullImgWidth, thumb.fullImgHeight))
  else:
    Log.Debug('++++ no size set - no resolution and no ratio bonus')

  # Get a bonus if image has a separate thumbnail URL.
  if thumb.thumbImgUrl is not None and thumb.fullImgUrl != thumb.thumbImgUrl:
    Log.Debug('++++ adding thumbnail bonus: +%d' % IMAGE_SCORE_THUMB_BONUS)
    score += IMAGE_SCORE_THUMB_BONUS

  Log.Debug('--------- SCORE: %d' % int(score))
  thumb.score = int(score)


def toInteger(maybeNumber):
  """ Returns the argument converted to an integer if it represents a number
      or None if the argument is None or does not represent a number.
  """
  try:
    if maybeNumber is not None and str(maybeNumber).strip() != '':
      return int(maybeNumber)
  except:
    pass
  return None


def computeTitlePenalty(mediaName, title):
  """ Given media name and a candidate title, returns the title result score penalty.
  """
  mediaName = mediaName.lower()
  title = title.lower()
  if mediaName != title:
    # Look for title word matches.
    words = mediaName.split()
    wordMatches = 0
    encodedTitle = title.encode(ENCODING_PLEX)
    for word in words:
      # NOTE(zhenya): using '\b' was troublesome (because of string encoding issues, I think).
      matcher = re.compile('^(|.*[\W«])%s([\W»].*|)$' % word.encode(ENCODING_PLEX), re.UNICODE)
      if matcher.search(encodedTitle) is not None:
        wordMatches += 1
    wordMatchesScore = float(wordMatches) / len(words)
    return int((float(1) - wordMatchesScore) * SCORE_PENALTY_TITLE)
  return 0


def getXpathOptionalNode(elem, xpath):
  """ Evaluates a given xpath expression against a given node and
      returns the first result or None if there are no results.
  """
  valueElems = elem.xpath(xpath)
  if len(valueElems) > 0:
    return valueElems[0]
  return None


def getXpathOptionalNodeStrings(elem, xpath):
  """ Evaluates a given xpath expression against a given node and
      returns non-empty strings from all results as an array.
  """
  textValues = elem.xpath(xpath)
  values = []
  for textValue in textValues:
    value = textValue.strip().strip(',')
    if len(value) > 0:
      values.append(value)
  return values


def getXpathRequiredNode(elem, xpath):
  """ Evaluates a given xpath expression against a given node and
      returns the first result. Throws an exception if there are no results.
  """
  value = getXpathOptionalNode(elem, xpath)
  if value is None:
    raise Exception('Unable to evaluate xpath "%s"' % str(xpath))
  return value


def getReOptionalGroup(matcher, str, groupInd):
  """ Evaluates a passed matcher against a given string and returns a group
      from the result with a given index. None is returned if there is no match
      or when the passed string argument is None.
  """
  if str is not None:
    match = matcher.search(str)
    if match is not None:
      groups = match.groups()
      if len(groups) > groupInd:
        return groups[groupInd]
  return None