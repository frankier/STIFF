Some WordNet/OpenSubtitles2018 related exploratory scripts

abbrvs.py - Find usages of grammatically meaningful abbreviations in FinnWordNet (verb + noun with case ending)
detect_chinese.py - Detect usage of traditional versus simplified Chinese in OpenSubtitles2018
confsmat.ipynb - Plot a confusion matrix of said scripts versus their classification in OpenSubtitles2018
diff.py - Test to see if tokenised and untokenised sentences can be realigned in OpenSubtitles2018
important.py - Get the most important words and multiwords in FinnWordNet as well as just the longest words
trace_wn.py - Spit out all WordNet lemmas found in STDIN

To make the confusion matrix plot:

  $ pipenv run python detect_chinese.py confsmat-analyse cmn-fin/OpenSubtitles2018/fi-zh_cn/OpenSubtitles2018.fi-zh_cn.zh_cn cmn-fin/OpenSubtitles2018/fi-zh_cn/OpenSubtitles2018.fi-zh_cn.ids cmn-fin/OpenSubtitles2018/fi-zh_tw/OpenSubtitles2018.fi-zh_tw.zh_tw cmn-fin/OpenSubtitles2018/fi-zh_tw/OpenSubtitles2018.fi-zh_tw.ids confsanalys.pkl
  $ pipenv run python detect_chinese.py confsmat-cls confsanalys.pkl confsmat4.pkl

Then run `confsmat.ipynb` with Jupyter notebook.
