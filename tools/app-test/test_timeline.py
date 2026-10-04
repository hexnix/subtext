"""Cards on the film's timeline (v43, picks A1, C1; v46: jump buttons instead of dots, a definitions pane): a made-up film in a made-up My Files, in a phone held sideways (915×412).

    python3 tools/app-test/test_timeline.py . --out shots/timeline/

Imports three made-up cards from "Made Up Film" (two with a line from the film's subtitles, one with only its scene time)
and one from another film, then checks that the player finds which film it is by its subtitles and says so once (A1), a blue
the two jump buttons under the title going to about 5 s before the next or previous card (v46), no dots on the seek bar,
the card notice when the film plays into a card (C1), a tap on it opening only the definition pages in a pane on the right
(the word and its core meaning, several pages one under another) and Back playing on, the choice kept when the film opens
again, "Cards from" in ⋯ (another film, None of these), a card made from a saved line joining the jumps, and JavaScript errors. Everything is invented: never put real films, subtitles or cards in the repo.
"""
import argparse, asyncio, base64, json, os, sys, tempfile, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Phone
from make_test_library import frame
from test_player import FILL_JS, FILM, SRT

KIT = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(KIT, 'fixtures', 'test-library.zip')
T0 = 1790000000000


def film_zip(path):
    def card(i, id, word, cap, t, show='Made Up Film', **kw):
        c = {'id': id, 'seq': i, 'word': word, 'addedAt': T0 + i, 'shotAt': T0 + i, 'sceneTime': t, 'scene': f'images/{id}.jpg',
             'definitions': [None], 'definitionText': [{'src': 'made up', 'kind': 'dictionary', 'blocks': [
                 {'t': 'headword', 'text': word}, {'t': 'def', 'text': 'A made-up meaning for a test.'}]}],
             'tags': ['Movie', show]}
        if cap: c['sceneCaption'] = cap
        c.update(kw); return c
    cs = [card(1, 'tl-report', 'shorter report', 'Then we write a\n==shorter report==.', 106.0),
          card(2, 'tl-numbers', 'numbers', None, 115.2),
          card(3, 'tl-candor', 'candor', 'Bring the ==candor==,\nleave the timing.', 124.5, definitions=[None, None], definitionText=[
              {'src': 'made up', 'kind': 'dictionary', 'blocks': [{'t': 'headword', 'text': 'candor'}, {'t': 'pron', 'text': '/ˈkan-dər/ made-up guide'},
                  {'t': 'def', 'text': 'Plain honesty, made up for a test.'}, {'t': 'ex', 'text': 'An example sentence that must not show.'}]},
              {'src': 'made up', 'kind': 'dictionary', 'blocks': [{'t': 'headword', 'text': 'candour'}, {'t': 'def', 'text': 'The second made-up page.'}]}]),
          card(4, 'tl-other', 'elsewhere', 'A line from ==another== film entirely.', 50.0, show='Another Made Up Film')]
    man = {'app': 'agora', 'version': 1, 'decks': [{'name': 'Vocabulary', 'cards': cs}]}
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('manifest.json', json.dumps(man))
        for i, c in enumerate(cs): z.writestr(c['scene'], frame(i + 2, 960, 540))


async def main(app, out):
    os.makedirs(out, exist_ok=True); tmp = tempfile.mkdtemp()
    fails = []
    def check(ok, what):
        print(('ok   ' if ok else 'FAIL ') + what)
        if not ok: fails.append(what)
    zp = os.path.join(tmp, 'film-cards.zip'); film_zip(zp)

    async with Phone(app, width=915, height=412) as ph:
        pg = ph.pg
        await ph.imp([LIB]); print('import:', await ph.imp([zp]))
        film = base64.b64encode(open(FILM, 'rb').read()).decode()
        await pg.evaluate(FILL_JS, [film, SRT])
        await pg.evaluate("T.connectFiles(true)")
        await pg.wait_for_function("T.FX.scanned && !T.FX.scanning", timeout=20000)

        async def open_film():
            await pg.evaluate("T.openFolder('Films')"); await pg.wait_for_timeout(500)
            await pg.locator('.page:last-child [data-fp="Films/Made Up Film.mkv"]').first.click()
            await pg.wait_for_function("T.PL && T.PL.cues.length >= 5 && T.PL.v.duration > 0", timeout=20000)
        await open_film()
        await pg.evaluate("T.PL.v.pause(); T.PL.v.currentTime = 1"); await pg.wait_for_timeout(2200)

        # A1: found by its subtitles, said once
        m = await pg.evaluate("T.PL.match && [T.PL.match.name, T.PL.match.cards.map(c => c.id), T.PL.rec.match]")
        print('  match:', m)
        check(m and m[0] == 'Made Up Film' and m[1] == ['tl-report', 'tl-numbers', 'tl-candor'] and m[2]['by'] == 'subtitles', 'the film is found by its subtitles, its cards in order')
        line = await pg.evaluate("(document.querySelector('.pl-match') || {}).textContent || ''")
        check('This is Made Up Film' in line and '3 cards' in line and 'Change' in line, f'a line says which film it is, with Change ({line})')
        await ph.shot(f'{out}/01-match-line.png')

        # v46: no dots; two jump buttons under the title
        await pg.evaluate("document.querySelector('.player').classList.add('ui')"); await pg.wait_for_timeout(300)
        j = await pg.evaluate("""(() => { const j = document.querySelector('.pl-jumps'), r = j.getBoundingClientRect(), t = document.querySelector('.pl-top').getBoundingClientRect();
          return [j.hidden, j.querySelectorAll('.pl-jb').length, r.top >= t.bottom - 30, !!document.querySelector('.pl-marks'), Math.round(j.querySelector('.pl-jb').getBoundingClientRect().width)]; })()""")
        check(j[:4] == [False, 2, True, False], f'two jump buttons under the title, no dots on the seek bar ({j})')
        await ph.shot(f'{out}/02-jump-buttons.png')
        moments = [6, 15.2, 24]
        await pg.evaluate("T.PL.v.currentTime = 0")
        ts = []
        for _ in range(4):
            await pg.locator('.pl-jb[data-p="tnext"]').click(); await pg.wait_for_timeout(250)
            ts.append(round(await pg.evaluate("T.PL.v.currentTime"), 1))
        check(ts == [1.0, 10.2, 19.0, 19.0], f'next goes to 5 s before each card in turn, and stops after the last ({ts})')
        ts = []
        for _ in range(3):
            await pg.locator('.pl-jb[data-p="tprev"]').click(); await pg.wait_for_timeout(250)
            ts.append(round(await pg.evaluate("T.PL.v.currentTime"), 1))
        check(ts == [10.2, 1.0, 1.0], f'previous goes back one card at a time ({ts})')
        await pg.evaluate("T.PL.v.currentTime = 3")
        await pg.locator('.pl-jb[data-p="tprev"]').click(); await pg.wait_for_timeout(250)
        check(round(await pg.evaluate("T.PL.v.currentTime"), 1) == 1.0, 'previous while the first word is still coming goes back to its start')

        # a line saved for a card (no dot for it)
        await pg.evaluate("T.PL.v.currentTime = 33.5"); await pg.wait_for_timeout(500)
        await pg.evaluate("document.querySelector('.player').classList.remove('ui')"); await pg.wait_for_timeout(400)
        await pg.locator('.pl-sub span').click(); await pg.wait_for_timeout(500)
        labels = await pg.evaluate("[...document.querySelectorAll('.pl-note [data-kind]')].map(b => b.textContent.trim())")
        check(labels == ['Define', 'Explain'], f'the save panel says Define and Explain ({labels})')
        await pg.locator('.pl-note [data-kind="vocabulary"]').click(); await pg.wait_for_timeout(1200)
        await pg.evaluate("T.PL.v.pause(); document.querySelectorAll('.pl-toast').forEach(t => t.remove())")

        # C1: playing into a card's moment; a tap opens its definitions in a pane
        await pg.evaluate("T.PL.v.currentTime = 22.8; T.PL.v.play()")
        await pg.wait_for_function("!!document.querySelector('.pl-card')", timeout=5000)
        cn = await pg.evaluate("[document.querySelector('.pl-card').dataset.id, document.querySelector('.pl-card').textContent]")
        check(cn[0] == 'tl-candor' and 'candor' in cn[1], f'reaching a card shows it at the top right ({cn})')
        await pg.wait_for_timeout(400)
        await ph.shot(f'{out}/03-card-notice.png')
        await pg.locator('.pl-card').click(); await pg.wait_for_timeout(700)
        pd = await pg.evaluate("""(() => { const p = document.querySelector('.pl-defs'), r = p.getBoundingClientRect();
          return [p.classList.contains('open'), T.PL.v.paused, document.querySelectorAll('.study').length, p.querySelectorAll('.t-headword').length,
            p.textContent, Math.round(r.left), innerWidth, getComputedStyle(p.querySelector('.t-headword')).fontSize]; })()""")
        print('  pane:', pd[4][:160])
        check(pd[0] and pd[1] and pd[2] == 0 and pd[5] > pd[6] / 2, f'a tap on it pauses the film and opens a pane on the right, not the study view ({pd[:3]}, {pd[5]})')
        check(pd[3] == 2 and 'Plain honesty' in pd[4] and 'second made-up page' in pd[4], 'both definition pages, one under the other')
        check('example sentence' not in pd[4] and 'made-up guide' not in pd[4] and 'Bring the' not in pd[4], 'only the word and its meaning: no pronunciation, examples, scene or source')
        check(pd[7] == '24px', f'the word sized for the pane ({pd[7]})')
        await ph.shot(f'{out}/04-definitions-pane.png')
        await pg.evaluate("document.querySelector('.pl-defs').scrollTop = 9999"); await pg.wait_for_timeout(200)
        await ph.shot(f'{out}/05-definitions-scrolled.png')
        await ph.back(); await pg.wait_for_timeout(600)
        back = await pg.evaluate("[document.querySelector('.pl-defs').classList.contains('open'), !!T.PL, T.PL && T.PL.v.paused, T.PL && Math.round(T.PL.v.currentTime)]")
        check(back[:3] == [False, True, False] and 23 <= back[3] <= 26, f'Back closes the pane and the film plays on ({back})')
        await pg.evaluate("T.PL.v.pause()")

        # it is remembered: no line the second time
        await ph.back(); await pg.wait_for_timeout(600)
        check(await pg.evaluate("!T.PL"), 'Back leaves the player')
        await open_film(); await pg.evaluate("T.PL.v.pause()"); await pg.wait_for_timeout(2200)
        again = await pg.evaluate("[T.PL.match && T.PL.match.name, !!document.querySelector('.pl-match'), T.PL.marks.length]")
        check(again == ['Made Up Film', False, 3], f'opened again, it remembers the film and says nothing ({again})')

        # ⋯ › Cards from: None of these, then another film, then back
        await pg.click('.player [data-p="more"]'); await pg.wait_for_timeout(500)
        menu = await pg.inner_text('#sheet')
        check('Cards from' in menu and 'Made Up Film' in menu, 'the ⋯ menu says where the cards come from')
        await pg.click('#sheet [data-act="match"]'); await pg.wait_for_timeout(600)
        sh = await pg.inner_text('#sheet'); print('  sheet:', sh.replace('\n', ' | '))
        check('✓ Made Up Film' in sh and 'Another Made Up Film' in sh and 'None of these' in sh, 'the sheet lists the films, this one ticked')
        await ph.shot(f'{out}/06-cards-from.png')
        await pg.click('#sheet [data-act="none"]'); await pg.wait_for_timeout(600)
        no = await pg.evaluate("[T.PL.match, T.PL.marks.length, document.querySelector('.pl-jumps').hidden, T.PL.rec.match]")
        check(no[0] is None and no[1] == 0 and no[2] and no[3].get('none'), f'None of these hides the jump buttons ({no[:3]})')
        await pg.click('.player [data-p="more"]'); await pg.wait_for_timeout(400)
        await pg.click('#sheet [data-act="match"]'); await pg.wait_for_timeout(500)
        await pg.locator('#sheet .item', has_text='Another Made Up Film').click(); await pg.wait_for_timeout(600)
        ot = await pg.evaluate("[T.PL.match && T.PL.match.name, T.PL.rec.match.by, T.PL.marks.length]")
        check(ot == ['Another Made Up Film', 'you', 1], f'picking another film shows its cards ({ot})')
        await pg.click('.player [data-p="more"]'); await pg.wait_for_timeout(400)
        await pg.click('#sheet [data-act="match"]'); await pg.wait_for_timeout(500)
        await pg.evaluate("[...document.querySelectorAll('#sheet [data-act]')].find(b => b.textContent.trim().startsWith('Made Up Film')).click()"); await pg.wait_for_timeout(600)
        check(await pg.evaluate("T.PL.match && T.PL.match.name") == 'Made Up Film', 'and back to this one')

        # a card made from the saved line joins the jumps
        nid = await pg.evaluate("[...T.CN.recs.values()][0].id")
        mz = os.path.join(tmp, 'made.zip')
        with zipfile.ZipFile(zp) as z0, zipfile.ZipFile(mz, 'w') as z:
            man = json.loads(z0.read('manifest.json'))
            c = dict(man['decks'][0]['cards'][2]); c.update(id='tl-last', seq=5, word='last line', sceneTime=133.0, scene='images/tl-last.jpg',
                                                         sceneCaption="That's the ==last line== of the film.", fromNote=nid)
            man['decks'][0]['cards'] = [c]; z.writestr('manifest.json', json.dumps(man)); z.writestr('images/tl-last.jpg', frame(7, 960, 540))
        await ph.back(); await pg.wait_for_timeout(500)
        print('made:', await ph.imp([mz]))
        await open_film(); await pg.evaluate("T.PL.v.pause()"); await pg.wait_for_timeout(2200)
        fin = await pg.evaluate("T.PL.marks.length")
        check(fin == 4, f'a card made from the saved line joins the jumps ({fin})')
        print('errors:', ph.errors)
        check(not ph.errors, 'no JavaScript errors')

    print('\nALL OK' if not fails else f'\n{len(fails)} FAILED')
    return 1 if fails else 0


if __name__ == '__main__':
    a = argparse.ArgumentParser(); a.add_argument('app'); a.add_argument('--out', default='shots/timeline')
    a = a.parse_args()
    sys.exit(asyncio.run(main(a.app, a.out)))
