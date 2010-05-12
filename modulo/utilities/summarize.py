#!/usr/bin/python
# -*- coding: iso-8859-1 -*-

'''Extracts the first few lines or characters from HTML text to
create a brief summary.'''

debug = False

# All HTML tags with block layout, i.e. that force line breaks
# before and after
block_tags = ('address', 'blockquote', 'center', 'code', 'div', 'dl', 'dt', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'isindex', 'li', 'menu', 'ol', 'p', 'table', 'tr', 'ul')
# All HTML tags which have corresponding close tags. This is the
# complete list of HTML 4.0 paired tags including non-strict tags
# and high-level elements which shouldn't occur in practice
paired_tags = ('a', 'abbr', 'acronym', 'address', 'applet', 'b', 'bdo', 'big', 'blockquote', 'body', 'button', 'caption', 'center', 'cite', 'code', 'colgroup', 'dd', 'del', 'dfn', 'div', 'dl', 'dt', 'em', 'fieldset', 'font', 'form', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'head', 'html', 'i', 'ins', 'kbd', 'label', 'latex', 'legend', 'li', 'map', 'math', 'menu', 'noframes', 'noscript', 'object', 'ol', 'optgroup', 'option', 'p', 'pre', 'q', 's', 'samp', 'script', 'select', 'small', 'span', 'strike', 'strong', 'style', 'sub', 'sup', 'table', 'tbody', 'td', 'textarea', 'tfoot', 'th', 'thead', 'title', 'tr', 'tt', 'u', 'ul', 'var')
# <math> and <latex> tags shouldn't have to be in this list but
# if it's the first thing in a post Markdown doesn't process it :(

def summarize(text, nlines = 4, cpl = 88):
    '''An HTML-aware version of the previous _autosummarize function.'''
    n = 0
    open_tags = []
    last_open_tag_action = None # True means a tag was just pushed, string means that tag was just popped
    lc = 0
    ll = 0
    lx = 0
    cur_tag = None
    cur_ent = None
    wordbreakpos = 0
    phrasebreakpos = 0
    ended_with_linebreak = True
    for c in text:
        if debug: print 'string so far: %s' % text[:n+1]
        if c == '<': # use '==', NOT 'is', because only == properly compares unicode and regular characters
            # opening of an HTML tag
            cur_tag = [n, 0]
            wordbreakpos = n
            if debug: print '  ---- setting wordbreakpos = %d' % (n)
        elif cur_tag:
            if (c.isspace() or c == '>') and cur_tag[1] == 0:
                # end of the tag name of an HTML tag
                cur_tag[1] = n + 1
                tag = text[cur_tag[0]+1:cur_tag[1]-1].strip().lower()
                if tag.startswith('/'):
                    # a closing tag
                    tag = tag[1:]
                    if open_tags[-1] == tag:
                        last_open_tag_action = open_tags.pop()
                        if debug: print '  ---* popping %s from open_tags' % last_open_tag_action
                    if tag in block_tags:
                        ll += 1
                        lx = 0
                        ended_with_linebreak = True
                        wordbreakpos = cur_tag[0]
                        phrasebreakpos = cur_tag[0]
                        if debug: print '  ---+ setting phrasebreakpos = %d, wordbreakpos = %d' % (cur_tag[0], cur_tag[0])
                elif tag in paired_tags:
                    # an opening tag
                    open_tags.append(tag)
                    last_open_tag_action = True
                    if debug: print '  --*- pushing %s to open_tags' % tag
                    if tag in block_tags:
                        if not ended_with_linebreak:
                            if ll > nlines: # because this tag isn't going to get included in the output
                                last_open_tag_action = open_tags.pop()
                                if debug: print '  --** popping %s from open_tags' % last_open_tag_action
                            ll += 1
                            lx = 0
                        wordbreakpos = cur_tag[0]
                        phrasebreakpos = cur_tag[0]
                        if debug: print '  --+- setting phrasebreakpos = %d, wordbreakpos = %d' % (cur_tag[0], cur_tag[0])
                elif tag == 'br':
                    if ll > nlines: # because this tag isn't going to get included in the output
                        last_open_tag_action = open_tags.pop()
                        if debug: print '  -*-- popping %s from open_tags' % last_open_tag_action
                    ll += 1
                    lx = 0
                    wordbreakpos = cur_tag[0]
                    phrasebreakpos = cur_tag[0]
                    if debug: print '  --++ setting phrasebreakpos = %d, wordbreakpos = %d' % (cur_tag[0], cur_tag[0])
            if c == '>':
                # close of an HTML tag
                cur_tag = None
        elif c == '&':
            # opening of an HTML entity
            cur_ent = [n+1, 0]
        elif cur_ent:
            if c == ';':
                # close of an HTML entity
                cur_ent[1] = n
                lc += 1
                lx += 1
                if lx == cpl:
                    ll += 1
                    lx = 0
                ended_with_linebreak = False
                cur_ent = None
        elif c in '.,;-':
            # these are characters we should insert a phrase break after
            phrasebreakpos = n+1
            wordbreakpos = n+1
            if debug: print '  -+-- setting phrasebreakpos = %d, wordbreakpos = %d' % (n+1, n+1)
            lc += 1
            lx += 1
            if lx == cpl:
                ll += 1
                lx = 0
            ended_with_linebreak = False
        elif c.isspace():
            # insert a word break before the space
            wordbreakpos = n
            if debug: print '  -+-+ setting wordbreakpos = %d' % (n)
            lc += 1
            if lx > 0:
                lx += 1
            if lx == cpl:
                ll += 1
                lx = 0
            #ended_with_linebreak = False
        else:
            lc += 1
            lx += 1
            if lx == cpl:
                ll += 1
                lx = 0
            ended_with_linebreak = False
        if ll >= nlines:
            # we've reached our line limit
            n += 1
            if n < len(text):
                if last_open_tag_action is True:
                    last_open_tag_action = open_tags.pop()
                    if debug: print '  -*-* popping %s from open_tags' % last_open_tag_action
                elif isinstance(last_open_tag_action, str):
                    open_tags.append(last_open_tag_action)
                    if debug: print '  -**- pushing %s to open_tags' % last_open_tag_action
            break
        last_open_tag_action = None
        n += 1
        if debug: print '  processed %d physical chars, %d logical chars, on line %d, ewl %s' % (n, lc, ll, ended_with_linebreak)
    assert n <= len(text)
    if n == len(text):
        summary = text[:n]
    elif phrasebreakpos and float(n - phrasebreakpos) / n > 0.97:
        summary = text[:phrasebreakpos] + '...'
    elif wordbreakpos:
        summary = text[:wordbreakpos] + '...'
    else:
        assert False
    open_tags.reverse()
    return summary + ''.join(map(lambda s: '</%s>' % s, open_tags))


def test1():
    print summarize('<p>test paragraph 1</p>some text<p>test paragraph 2</p>', nlines = 2, cpl = 30)

def test2():
    print summarize('<p>short</p><p>short</p><p>short</p><p>short</p><p>short</p>', nlines = 4, cpl = 30)

def test3():
    print summarize('<p>short</p><p>short</p><p>short</p><p>short</p><p>short</p>', nlines = 5, cpl = 30)

def test4():
    print summarize('<p>a really really long line of text that should just get cut off somewhere in the middle because of the product of nlines and cpl which is going to be less than the number of characters in this line</p>', nlines = 3, cpl = 30)

def test5():
    print summarize('<p>short</p><p>short</p><p>a really really long line of text that should just get cut off somewhere in the middle because of the product of nlines and cpl which is going to be less than the number of characters in this line</p>', nlines = 3, cpl = 30)

def test6(): # this one yields one line short
    print summarize('''<p>testing something</p>
<p>with multiple lines</p>
<p>that correspond to the paragraph breaks</p>
<p>here's another paragraph</p>''', nlines = 3, cpl = 50)

def test7():
    print summarize('''<p>testing something
with multiple lines</p><p>that DON'T
correspond to the</p><p>paragraph breaks</p><p>
here's another paragraph
</p>''', nlines = 3, cpl = 50)

def test8():
    print summarize('''something with inline tags with attributes <img src="/images/null.png"> and also
missing some paragraph tags''', nlines = 3, cpl = 40)

def test9():
    print summarize('''<p>This is a post with lots of text that is hopefully going to get wrapped by the summary generator because there are so many words in it. It needs to be at least four by eighty-eight characters long. Here are some more words of text and more words and more words and more words and more words. But it's not long enough yet so we keep typing more words and more words and more words and more words.
</p>''')

def test10():
    print summarize('''<p>Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text ever since the 1500s, when an unknown printer took a galley of type and scrambled it to make a type specimen book. It has survived not only five centuries, but also the leap into electronic typesetting, remaining essentially unchanged. It was popularised in the 1960s with the release of Letraset sheets containing Lorem Ipsum passages, and more recently with desktop publishing software like Aldus PageMaker including versions of Lorem Ipsum.
</p>
<p>There are many variations of passages of Lorem Ipsum available, but the majority have suffered alteration in some form, by injected humour, or randomised words which don't look even slightly believable. If you are going to use a passage of Lorem Ipsum, you need to be sure there isn't anything embarrassing hidden in the middle of text. All the Lorem Ipsum generators on the Internet tend to repeat predefined chunks as necessary, making this the first true generator on the Internet. It uses a dictionary of over 200 Latin words, combined with a handful of model sentence structures, to generate Lorem Ipsum which looks reasonable. The generated Lorem Ipsum is therefore always free from repetition, injected humour, or non-characteristic words etc.
</p>
''')

def test10u():
    print summarize(u'''<p>Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text ever since the 1500s, when an unknown printer took a galley of type and scrambled it to make a type specimen book. It has survived not only five centuries, but also the leap into electronic typesetting, remaining essentially unchanged. It was popularised in the 1960s with the release of Letraset sheets containing Lorem Ipsum passages, and more recently with desktop publishing software like Aldus PageMaker including versions of Lorem Ipsum.
</p>
<p>There are many variations of passages of Lorem Ipsum available, but the majority have suffered alteration in some form, by injected humour, or randomised words which don't look even slightly believable. If you are going to use a passage of Lorem Ipsum, you need to be sure there isn't anything embarrassing hidden in the middle of text. All the Lorem Ipsum generators on the Internet tend to repeat predefined chunks as necessary, making this the first true generator on the Internet. It uses a dictionary of over 200 Latin words, combined with a handful of model sentence structures, to generate Lorem Ipsum which looks reasonable. The generated Lorem Ipsum is therefore always free from repetition, injected humour, or non-characteristic words etc.
</p>
''')

def test():
    test1()
    print
    test2()
    print
    test3()
    print
    test4()
    print
    test5()
    print
    test6()
    print
    test7()
    print
    test8()

if __name__ == '__main__':
    debug = False
    test()
