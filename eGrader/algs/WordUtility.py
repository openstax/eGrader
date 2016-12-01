# -*- coding: utf-8 -*-
"""
Created on Thu Jan 14 21:11:03 2016

@author: drew
"""

#!/usr/bin/env python

import re
import pandas as pd
from nltk.corpus import stopwords
from nltk.corpus import words
from nltk.stem.snowball import SnowballStemmer
import collections
import string


class WordUtility(object):

    def __init__(self,
                 corpora_list=['all_plaintext.txt', 'big.txt'],
                 parse_args=(True, True, True, True, True)):

        #Set the parsing arguments
        self.remove_stopwords = parse_args[0]
        self.tag_numeric = parse_args[1]
        self.correct_spelling = parse_args[2]
        self.kill_nonwords = parse_args[3]
        self.stem = parse_args[4]

        #Alphabet
        self.alphabet = 'abcdefghijklmnopqrstuvwxyz'

        #Punctuation
        self.punc_dict = {ord(c): None for c in string.punctuation}

        #Reserved tags
        self.reserved_tags = ['numeric_type_hex',
                              'numeric_type_binary',
                              'numeric_type_octal',
                              'numeric_type_float',
                              'numeric_type_int',
                              'numeric_type_complex',
                              'numeric_type_roman',
                              'math_type']

        #Update the set of nltk words with the additional corpora
        self.all_words = set(words.words())
        self.all_words.update('a')
        self.all_words.update('i')
        self.all_words.update(self.reserved_tags)
        self.max_word_length = 20

        #Set up the stopwords, remove 'a' due to math issues
        self.stops = set(stopwords.words("english"))
        self.stops.remove('a')
        self.stops.remove('no')

        #Set up the stemmer
        self.st = SnowballStemmer('english')

        #Train the spelling corrector using all corpora
        train_text = ''
        for cfile in corpora_list:
            words_in_file = file(cfile).read()
            self.all_words.update(self.get_all_words(file(cfile).read()))
            train_text = train_text + words_in_file

        #Remove single character terms
        wordlist = list(self.all_words)
        wordlist = [i for i in wordlist if len(i) > 1]
        self.all_words = set(wordlist)
        self.all_words.update('a')
        self.all_words.update('i')

        self.NWORDS = self.train(self.get_all_words(train_text))

    def get_all_words(self, text):
        return re.findall('[a-z]+', text.lower())

    def train(self, features):
        model = collections.defaultdict(lambda: 1)
        for f in features:
            model[f] += 1
        return model

    def spell_correct(self, word):
        if (self.is_numeric(word) in self.reserved_tags):
            return word
        if (len(word) <= 3):
            return word
        else:
            candidates = self.known([word]) or self.known(self.edits1(word)) or self.known_edits2(word) or [word]
            return max(candidates, key=self.NWORDS.get)

    def known(self, words):
        return set(w for w in words if w in self.NWORDS)

    def edits1(self, word):
        s = [(word[:i], word[i:]) for i in range(len(word) + 1)]
        deletes    = [a + b[1:] for a, b in s if b]
        transposes = [a + b[1] + b[0] + b[2:] for a, b in s if len(b)>1]
        replaces   = [a + c + b[1:] for a, b in s for c in self.alphabet if b]
        inserts    = [a + c + b     for a, b in s for c in self.alphabet]
        return set(deletes + transposes + replaces + inserts)

    def known_edits2(self, word):
        return set(e2
                   for e1 in self.edits1(word)
                   for e2 in self.edits1(e1)
                   if e2 in self.NWORDS)

    def answer_to_wordlist(self,
                           answer):

        #Get the response text and parse into words
        answer_text = answer
        if(pd.isnull(answer_text)):
            answer_text = ''
        wordlist = answer_text.lower().split()
        wordlist = [unicode(w, errors='ignore') for w in wordlist]
        wordlist = [w[0:min(self.max_word_length, len(w))] for w in wordlist]


        if (len(wordlist) == 0):
            return(list(['no_text']))

        #Remove stopwords if applicable
        if self.remove_stopwords:
            wordlist = [w for w in wordlist if not w in self.stops]

        #Identify numeric values or math and tag appropriately
        #If we are not tagging math, we strip punctuation instead
        if self.tag_numeric:
            wordlist = [self.is_numeric(w) for w in wordlist]
        else:
            wordlist = [w.translate(self.punc_dict) for w in wordlist]

        if self.correct_spelling:
            #wordlist = [Word(w).spellcheck()[0][0] for w in wordlist]
            wordlist = [self.spell_correct(w) for w in wordlist]

        if self.kill_nonwords:
            wordlist = [
                        w
                        if w in self.all_words
                        or self.st.stem(w) in self.all_words
                        or self.is_numeric(w) in self.reserved_tags
                        or w in self.reserved_tags
                        else 'nonsense_word' for w in wordlist]

        if self.stem:
            wordlist = [self.st.stem(w) for w in wordlist]
            
        if (len(wordlist) == 0):
            return(list(['no_text']))

        return(wordlist)

    @staticmethod
    def is_numeric(lit):
        'Return either the type of string if numeric else return string'

        if (len(lit) == 0):
            return lit

        # Handle '0'
        if lit == '0':
            return "numeric_type_0"
        # Hex/Binary
        litneg = lit[1:] if (lit[0] == '-' and len(lit) > 1) else lit
#        if litneg[0] == '0':
#            if litneg[1] in 'xX':
#                try:
#                    temp = int(lit, 16)
#                    return 'numeric_type_hex'
#                except ValueError:
#                    pass
#            elif litneg[1] in 'bB':
#                try:
#                    temp = int(lit, 2)
#                    return 'numeric_type_binary'
#                except ValueError:
#                    pass
#            else:
#                try:
#                    temp = int(lit, 8)
#                    return 'numeric_type_octal'
#                except ValueError:
#                    pass

        # Int/Float/Complex/Roman
        try:
            temp = int(lit)
            return 'numeric_type_int'
        except ValueError:
            pass
        try:
            temp = float(lit)
            return 'numeric_type_float'
        except ValueError:
            pass
        try:
            temp = complex(lit)
            return 'numeric_type_complex'
        except ValueError:
            pass
#        try:
#            'Return either the type of string if math else return string'
#            a=b=c=d=e=f=g=h=i=j=k=l=m=n=o=p=q=r=s=t=u=v=w=x=y=z=1
#            A=B=C=D=E=F=G=H=I=J=K=L=M=N=O=P=Q=R=S=T=U=V=W=X=Y=Z=1
#            pi = 3.14;
#            temp_lit = lit
#
#            #These three replaces are just to fake out Python . . .
#            temp_lit.replace('^', '**')
#            temp_lit.replace('=', '==')
#            temp_lit.replace('_', '')
#
#            #Find all number-letter-number combos and replace with a single var
#            temp_lit = re.sub('\d*[a-zA-z]\d*', 'x', temp_lit)
#
#            eval(temp_lit)
#            return('math_type')
#        except:
#            pass
        try:

            class RomanError(Exception):
                pass

            class OutOfRangeError(RomanError):
                pass

            class NotIntegerError(RomanError):
                pass

            class InvalidRomanNumeralError(RomanError):
                pass

            #Define digit mapping
            romanNumeralMap = (('M',  1000),
                               ('CM', 900),
                               ('D',  500),
                               ('CD', 400),
                               ('C',  100),
                               ('XC', 90),
                               ('L',  50),
                               ('XL', 40),
                               ('X',  10),
                               ('IX', 9),
                               ('V',  5),
                               ('IV', 4),
                               ('I',  1))

            #Define pattern to detect valid Roman numerals
            romanNumeralPattern = re.compile("""
            ^                   # beginning of string
            M{0,4}              # thousands - 0 to 4 M's
            (CM|CD|D?C{0,3})    # hundreds - 900 (CM), 400 (CD), 0-300 (0 to 3 C's),
                                #            or 500-800 (D, followed by 0 to 3 C's)
            (XC|XL|L?X{0,3})    # tens - 90 (XC), 40 (XL), 0-30 (0 to 3 X's),
                                #        or 50-80 (L, followed by 0 to 3 X's)
            (IX|IV|V?I{0,3})    # ones - 9 (IX), 4 (IV), 0-3 (0 to 3 I's),
                                #        or 5-8 (V, followed by 0 to 3 I's)
            $                   # end of string
            """ , re.VERBOSE)

            lit_upper = lit.upper()
            if not lit_upper:
                raise InvalidRomanNumeralError, 'Input can not be blank'
            if not romanNumeralPattern.search(lit_upper):
                raise InvalidRomanNumeralError, 'Invalid Roman numeral: %s' % lit_upper

            result = 0
            index = 0
            for numeral, integer in romanNumeralMap:
                while lit_upper[index:index+len(numeral)] == numeral:
                    result += integer
                    index += len(numeral)
            return 'numeric_type_roman'
        except:
            return(lit)
