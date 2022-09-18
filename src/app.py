from glob import glob
from math import floor as m_floor
from os.path import isfile, expanduser
from re import fullmatch
from urllib.parse import quote_plus
from time import gmtime, strftime
import pandas as pd
from flask import Flask, render_template, request, redirect


DATA_DIR = f'{expanduser("~")}/data/'
PLOT_DIR = f'{expanduser("~")}/plots/'


app = Flask(__name__)

app.jinja_env.lstrip_blocks = True
app.jinja_env.trim_blocks = True


def make_rc_link(change_tag:str) -> str:
    return f'https://www.wikidata.org/wiki/Special:RecentChanges?reviewStatus=unpatrolled&limit=500&days=30&enhanced=1&tagfilter={quote_plus(change_tag)}'


def make_patrol_log_link(username:str) -> str:
    return f'https://www.wikidata.org/wiki/Special:Log?type=patrol&user={quote_plus(username.replace(" ", "_"))}'


def make_property_link(prop:str) -> str:
    return f'https://www.wikidata.org/wiki/Property:{prop}'


def make_item_link(item:str) -> str:
    return f'https://www.wikidata.org/wiki/{item}'


def make_revision_history_link(item:str) -> str:
    return f'https://www.wikidata.org/w/index.php?action=history&title={item}'


def make_rfd_deeplink(item:str) -> str:
    return f'https://www.wikidata.org/wiki/Wikidata:Requests_for_deletions#{item}'


def make_contributions_link(username:str) -> str:
    return f'https://www.wikidata.org/wiki/Special:Contributions/{quote_plus(username.replace(" ", "_"))}'


def make_diff_link(rev_id:str) -> str:
    return f'https://www.wikidata.org/wiki/Special:Diff/{rev_id}'


def fmt_full_page_title(page_title:str, namespace:str) -> str:
    if namespace=='':
        return page_title.replace('_', ' ')

    return f'{namespace}:{page_title.replace("_", " ")}'


def fmt_full_page_url(page_title:str, namespace:str) -> str:
    return f'https://www.wikidata.org/wiki/{fmt_full_page_title(page_title, namespace).replace(" ", "_")}'


def fmt_source(source:str) -> str:
    sources = {
        'mw.edit' : '',
        'mw.new' : 'N'
    }

    return sources.get(source, '?')


def calc_patrol_progress(values:pd.Series) -> int:
    return round(values['patrolled'] / values['total'] * 100)


def get_days(value:int) -> int:
    return m_floor(value / 86400)


def get_hours(value:int) -> int:
    return m_floor((value - (get_days(value)*86400)) / 3600)


def get_minutes(value:int) -> int:
    return m_floor((value - (get_days(value)*86400) - (get_hours(value)*3600)) / 60)


def get_seconds(value:int) -> int:
    return round(value % 60)


def fmt_patrol_delay(value:int) -> str:
    if value < 60:
        return f'{get_seconds(value)} s'
    elif value < 3600:
        return f'{get_minutes(value)} min {get_seconds(value)} s'
    elif value < 3600 * 6:
        return f'{get_hours(value)} h {get_minutes(value)} min {get_seconds(value)} s'
    elif value < 3600 * 24:
        return f'{get_hours(value)} h {get_minutes(value)} min'
    elif value < 3600 * 96:
        return f'{get_days(value)} d {get_hours(value)} h {get_minutes(value)} min'
    else:
        return f'{get_days(value)} d {get_hours(value)} h'


@app.route('/')
def index() -> str:
    with open(f'{DATA_DIR}update.txt', mode='r', encoding='utf8') as file_handle:
        update = file_handle.read()
        update_formatted = strftime('%Y-%m-%d, %H:%M:%S', gmtime(int(update)) )

    with open(f'{DATA_DIR}progress.txt', mode='r', encoding='utf8') as file_handle:
        progress = file_handle.read()

    with open(f'{DATA_DIR}todayProgress.txt', mode='r', encoding='utf8') as file_handle:
        today_progress = file_handle.read()

    with open(f'{DATA_DIR}progressRaw.txt', mode='r', encoding='utf8') as file_handle:
        progress_raw = file_handle.read()
        patrolled, edits = progress_raw.split('\t')
        progress_percent = int(patrolled) / int(edits) * 100

    with open(f'{DATA_DIR}todayProgressRaw.txt', mode='r', encoding='utf8') as file_handle:
        today_progress_raw = file_handle.read()
        today_patrolled, today_edits = today_progress_raw.split('\t')
        today_progress_percent = int(today_patrolled) / int(today_edits) * 100

    return render_template(
        'index.html',
        update=update_formatted,
        progress=progress,
        today_progress=today_progress,
        progress_percent=progress_percent,
        today_progress_percent=today_progress_percent
    )


@app.route('/patrol')
def patrol() -> str:
    return render_template(
        'patrol.html',
        title='About patrol'
    )


@app.route('/about')
def about() -> str:
    return render_template(
        'about.html',
        title='About this tool'
    )


@app.route('/changetags')
def changetags() -> str:
    data = pd.read_csv(
        f'{DATA_DIR}change-tags.tsv',
        sep='\t',
        skiprows=1,
        names=[ 'change_tag', 'cnt' ],
        dtype={ 'change_tag' : str, 'cnt' : int }
    )
    data['rc_link'] = data['change_tag'].apply(func=make_rc_link)

    return render_template(
        'changetags.html',
        title='Change tags',
        data=data
    )


@app.route('/editsummaries')
def edit_summaries() -> str:
    data = pd.read_csv(
        f'{DATA_DIR}actions.txt',
        sep='\t',
        skiprows=0,
        names=[ 'group_name', 'group_members' ],
        dtype={ 'group_name' : str, 'group_members' : str }
    )

    meta_group_names = [ 'none', 'terms', 'allclaims', 'allsitelinks' ]

    groups = data.loc[~data['group_name'].isin(meta_group_names)]
    meta_groups = data.loc[data['group_name'].isin(meta_group_names)]

    explain = pd.DataFrame({
        'group_name' : meta_group_names,
        'explain' : [
            'No “magic edit summary” as in some undo actions, or a “magic edit summary” that is not member of any group above',
            '<span class="tt">label + description + alias + anyterms</span>; everything that involves editing terms',
            '<span class="tt">claim + qualifier + reference</span>; everything that involves editing statements',
            '<span class="tt">sitelink + sitelinkmove</span>; everything that involves editing sitelinks'
        ]
    })

    meta_groups = meta_groups.merge(right=explain, on='group_name')

    return render_template(
        'actions.html',
        title='Magic edit summaries',
        groups=groups,
        meta_groups=meta_groups
    )


@app.route('/oresquality')
def ores_quality() -> str:
    return render_template(
        'oresquality.html',
        title='ORES model quality'
    )


@app.route('/patrollers')
def patrollers() -> str:
    with open(f'{DATA_DIR}progress.txt', mode='r', encoding='utf8') as file_handle:
        progress = file_handle.read()

    data = pd.read_csv(
        f'{DATA_DIR}top-patrollers-head.tsv',
        sep='\t',
        skiprows=1,
        usecols=[ 1, 2, 3 ],
        names=[ 'username', 'patrols', 'patrols_relative' ],
        dtype={ 'username' : str, 'patrols' : int, 'patrols_relative' : float }
    )
    data['patrol_log_link'] = data['username'].apply(func=make_patrol_log_link)

    return render_template(
        'patrollers.html',
        title='Top patrollers',
        progress=progress,
        data=data
    )


@app.route('/temp')
def temporal() -> str:
    return render_template(
        'temp.html',
        title='Temporal edit patterns'
    )


@app.route('/editorial')
def editorial() -> str:
    return render_template(
        'editorial.html',
        title='Editorial edit patterns'
    )


@app.route('/technical')
def technical() -> str:
    return render_template(
        'technical.html',
        title='Technical edit patterns'
    )


@app.route('/languages')
def languages() -> str:
    data = pd.read_csv(
        f'{DATA_DIR}plot-language-full.tsv',
        sep='\t',
        skiprows=1,
        names=[ 'language', 'unpatrolled', 'patrolled', 'total' ],
        dtype={ 'language' : str, 'unpatrolled' : int, 'patrolled' : int, 'total' : int }
    )
    data['progress'] = data[['patrolled', 'total']].apply(func=calc_patrol_progress, axis=1)
    data['rank'] = data['total'].rank(method='min', ascending=False)
    data['rank'] = data['rank'].astype(int)

    return render_template(
        'languages.html',
        title='Languages',
        data=data
    )


@app.route('/sitelinks')
def sitelinks() -> str:
    data = pd.read_csv(
        f'{DATA_DIR}plot-sitelink-full.tsv',
        sep='\t',
        skiprows=1,
        names=[ 'project', 'unpatrolled', 'patrolled', 'total' ],
        dtype={ 'project' : str, 'unpatrolled' : int, 'patrolled' : int, 'total' : int }
    )
    data['progress'] = data[['patrolled', 'total']].apply(func=calc_patrol_progress, axis=1)
    data['rank'] = data['total'].rank(method='min', ascending=False)
    data['rank'] = data['rank'].astype(int)

    return render_template(
        'sitelinks.html',
        title='Sitelinks',
        data=data
    )


@app.route('/properties')
def properties() -> str:
    data = pd.read_csv(
        f'{DATA_DIR}plot-property-full.tsv',
        sep='\t',
        skiprows=1,
        usecols=[ 1, 2, 3, 4, 5, 6 ],
        names=[ 'unpatrolled', 'patrolled', 'total', 'property', 'label', 'datatype' ],
        dtype={ 'unpatrolled' : int, 'patrolled' : int, 'total' : int, 'property' : str, 'label' : str, 'datatype' : str }
    )
    data['progress'] = data[['patrolled', 'total']].apply(func=calc_patrol_progress, axis=1)
    data['propertylink'] = data['property'].apply(func=make_property_link)
    data['rank'] = data['total'].rank(method='min', ascending=False)
    data['rank'] = data['rank'].astype(int)

    return render_template(
        'properties.html',
        title='Properties',
        data=data
    )


@app.route('/items')
def items() -> str:
    data = pd.read_csv(
        f'{DATA_DIR}worklist-items-many-revisions-head.tsv',
        sep='\t',
        skiprows=1,
        usecols=[ 1, 2 ],
        names=[ 'item', 'unpatrolled' ],
        dtype={ 'item' : str, 'unpatrolled' : int }
    )
    data['item_link'] = data['item'].apply(func=make_item_link)
    data['rev_history_link'] = data['item'].apply(func=make_revision_history_link)

    return render_template(
        'items.html',
        title='Many unpatrolled revisions',
        data=data
    )


@app.route('/highuse')
def highly_used() -> str:
    data = pd.read_csv(
        f'{DATA_DIR}worklist-highly-used-items-head.tsv',
        sep='\t',
        skiprows=1,
        names=[ 'item', 'entity_usage', 'unpatrolled' ],
        dtype={ 'item' : str, 'entity_usage' : int, 'unpatrolled' : int }
    )
    data['item_link'] = data['item'].apply(func=make_item_link)
    data['rev_history_link'] = data['item'].apply(func=make_revision_history_link)

    return render_template(
        'highuse.html',
        title='Highly used items',
        data=data
    )


@app.route('/rfdlinked')
def rfd_linked() -> str:
    data = pd.read_csv(
        f'{DATA_DIR}wdrfd-linked-full.tsv',
        sep='\t',
        skiprows=1,
        usecols=[ 1, 2, 3, 4, 5, 6, 7, 8 ],
        names=[ 'patrol_ratio', 'unpatrolled', 'item', 'label', 'statements', 'identifiers', 'sitelinks', 'backlinks' ],
        dtype={ 'patrol_ratio' : float, 'unpatrolled' : int, 'item' : str, 'label' : str, 'statements' : int, 'identifiers' : int, 'sitelinks' : int, 'backlinks' : int }
    )
    data['patrol_ratio'] = data['patrol_ratio']*100
    data['patrol_ratio'] = data['patrol_ratio'].astype(int)
    data['item_link'] = data['item'].apply(func=make_item_link)
    data['rev_history_link'] = data['item'].apply(func=make_revision_history_link)
    data['rfd_deeplink'] = data['item'].apply(func=make_rfd_deeplink)

    line_cnt = data.shape[0]
    rev_cnt = data['unpatrolled'].sum()

    return render_template(
        'rfdlinked.html',
        title='Items linked from WD:RfD',
        data=data,
        line_cnt=line_cnt,
        rev_cnt=rev_cnt
    )


@app.route('/uncategorizable')
def uncategorizable() -> str:
    try:
        data = pd.read_csv(
            f'{DATA_DIR}worklist-uncategorizable-editsummaries-full.tsv',
            sep='\t',
            skiprows=1,
            usecols=[ 1, 2, 3, 4, 5 ],
            names=[ 'rc_id', 'rc_timestamp', 'item', 'rc_this_oldid', 'username' ],
            dtype={ 'rc_id' : int, 'rc_timestamp' : int, 'item' : str, 'rc_this_oldid' : int, 'username' : str }
        )
    except FileNotFoundError:
        data = None
    else:
        data['timestamp'] = pd.to_datetime(data['rc_timestamp'], format='%Y%m%d%H%M%S')
        data['item_link'] = data['item'].apply(func=make_item_link)
        data['timestamp_formatted'] = data['timestamp'].dt.strftime(date_format='%Y-%m-%d, %H:%M:%S')
        data['diff_link'] = data['rc_this_oldid'].apply(func=make_diff_link)
        data['contributions_link'] = data['username'].apply(func=make_contributions_link)

    return render_template(
        'uncategorizable.html',
        title='Uncategorizable edit summaries',
        data=data
    )


@app.route('/ores')
def ores() -> str:
    data_unregistered = pd.read_csv(
        f'{DATA_DIR}worklist-ores-head.tsv',
        sep='\t',
        skiprows=1,
        names=[ 'username', 'unpatrolled', 'ores_avg' ],
        dtype={ 'username' : str, 'unpatrolled' : int, 'ores_avg' : float }
    )
    data_unregistered['contributions_link'] = data_unregistered['username'].apply(func=make_contributions_link)

    data_registered = pd.read_csv(
        f'{DATA_DIR}worklist-ores-head-registered.tsv',
        sep='\t',
        skiprows=1,
        names=[ 'username', 'unpatrolled', 'ores_avg' ],
        dtype={ 'username' : str, 'unpatrolled' : int, 'ores_avg' : float }
    )
    data_registered['contributions_link'] = data_registered['username'].apply(func=make_contributions_link)

    return render_template(
        'ores.html',
        title='High average ORES scores',
        unregistered=data_unregistered,
        registered=data_registered
    )


@app.route('/suggested')
def suggested() -> str:
    data = pd.read_csv(
        f'{DATA_DIR}worklist-head-suggested-edit.tsv',
        sep='\t',
        skiprows=1,
        usecols=[ 1, 2, 3, 4, 5, 6, 7, 8 ],
        names=[ 'username', 'patrolled', 'unpatrolled', 'reverted', 'created', 'total', 'patrolled_ratio', 'reverted_ratio' ],
        dtype={ 'username' : str, 'patrolled' : int, 'unpatrolled' : int, 'reverted' : int, 'created' : int, 'total' : int, 'patrolled_ratio' : float, 'reverted_ratio' : float }
    )
    data['contributions_link'] = data['username'].apply(func=make_contributions_link)
    data['patrolled_ratio'] = data['patrolled_ratio'].astype(int)
    data['reverted_ratio'] = data['reverted_ratio'].astype(int)

    return render_template(
        'suggested.html',
        title='Suggested edits',
        data=data
    )


@app.route('/creations')
def creations() -> str:
    data = pd.read_csv(
        f'{DATA_DIR}worklist-users-with-many-creations-head.tsv',
        sep='\t',
        skiprows=1,
        names=[ 'username', 'creations' ],
        dtype={ 'username' : str, 'creations' : int }
    )
    data['contributions_link'] = data['username'].apply(func=make_contributions_link)

    return render_template(
        'creations.html',
        title='Many creations',
        data=data
    )


@app.route('/by_time')
@app.route('/by_time/<string:timeframe>')
def by_time(timeframe='today') -> str:
    try:
        data = pd.read_csv(
            f'{DATA_DIR}worklist-head-{timeframe}.tsv',
            sep='\t',
            skiprows=1,
            usecols=[ 1, 2, 3, 4, 5, 6, 7, 8 ],
            names=[ 'username', 'patrolled', 'unpatrolled', 'reverted', 'created', 'edits', 'patrolled_ratio', 'reverted_ratio' ],
            dtype={ 'username' : str, 'patrolled' : int, 'unpatrolled' : int, 'reverted' : int, 'created' : int, 'edits' : int, 'patrolled_ratio' : float, 'reverted_ratio' : float }
        )
    except FileNotFoundError:
        data = None
    else:
        data['contributions_link'] = data['username'].apply(func=make_contributions_link)
        data['patrolled_ratio'] = data['patrolled_ratio'].astype(int)
        data['reverted_ratio'] = data['reverted_ratio'].astype(int)

    descriptions = {
        'all' : 'in the past 30 days',
		'14d' : 'in the past 14 days',
		'7d' : 'in the past 7 days',
		'3d' : 'in the past 3 days',
        'today' : 'today'
    }

    return render_template(
        'by_time.html',
        title='Unpatrolled changes by timeframe',
        timeframe=timeframe,
        data=data,
        description=descriptions.get(timeframe)
    )


@app.route('/by_project', methods=['GET', 'POST'])
@app.route('/by_project/<string:project>')
def by_project(project='dewiki'):  #  -> Union[str, .wrappers.Response]
    if request.method == 'POST':
        return redirect(f'/by_project/{request.form.get("project")}')


    projects = []
    for sitelink_change in glob(f'{DATA_DIR}page/worklist-*-page-full.tsv'):
        match = fullmatch(fr'^{DATA_DIR}page/worklist-(.*)-page-full.tsv$', sitelink_change)
        if match is not None:
            projects.append(match.group(1))
    for page_move in glob(f'{DATA_DIR}pagemove/worklist-*-pagemove-full.tsv'):
        match = fullmatch(fr'^{DATA_DIR}pagemove/worklist-(.*)-pagemove-full.tsv$', page_move)
        if match is not None:
            projects.append(match.group(1))
    for page_removal in glob(f'{DATA_DIR}pageremoval/worklist-*-pageremoval-full.tsv'):
        match = fullmatch(fr'^{DATA_DIR}pageremoval/worklist-(.*)-pageremoval-full.tsv$', page_removal)
        if match is not None:
            projects.append(match.group(1))
    projects = sorted(list(set(projects)))


    try:
        sitelink_df = pd.read_csv(
            f'{DATA_DIR}page/worklist-{project}-page-full.tsv',
            sep='\t',
            skiprows=1,
            usecols=[ 1, 2, 3, 4, 5, 6, 7, 8 ],
            names=[ 'rc_id', 'rc_timestamp', 'item', 'rc_this_oldid', 'username', 'oresc_damaging', 'oresc_goodfaith', 'editsummary_magic_action' ],
            dtype={ 'rc_id' : int, 'rc_timestamp' : int, 'item' : str, 'rc_this_oldid' : int, 'username' : str, 'oresc_damaging' : float, 'oresc_goodfaith' : float, 'editsummary_magic_action' : str }
        )
    except FileNotFoundError:
        sitelink_df = None
    else:
        sitelink_df['timestamp'] = pd.to_datetime(sitelink_df['rc_timestamp'], format='%Y%m%d%H%M%S')
        sitelink_df['item_link'] = sitelink_df['item'].apply(func=make_item_link)
        sitelink_df['timestamp_formatted'] = sitelink_df['timestamp'].dt.strftime(date_format='%Y-%m-%d, %H:%M:%S')
        sitelink_df['diff_link'] = sitelink_df['rc_this_oldid'].apply(func=make_diff_link)
        sitelink_df['contributions_link'] = sitelink_df['username'].apply(func=make_contributions_link)


    try:
        pagemoves = pd.read_csv(
            f'{DATA_DIR}pagemove/worklist-{project}-pagemove-full.tsv',
            sep='\t',
            skiprows=1,
            usecols=[ 1, 2, 3, 4, 5, 6, 7, 8 ],
            names=[ 'rc_id', 'rc_timestamp', 'item', 'rc_this_oldid', 'username', 'oresc_damaging', 'oresc_goodfaith', 'editsummary_magic_action' ],
            dtype={ 'rc_id' : int, 'rc_timestamp' : int, 'item' : str, 'rc_this_oldid' : int, 'username' : str, 'oresc_damaging' : float, 'oresc_goodfaith' : float, 'editsummary_magic_action' : str }
        )
    except FileNotFoundError:
        pagemoves = None
    else:
        pagemoves['timestamp'] = pd.to_datetime(pagemoves['rc_timestamp'], format='%Y%m%d%H%M%S')
        pagemoves['item_link'] = pagemoves['item'].apply(func=make_item_link)
        pagemoves['timestamp_formatted'] = pagemoves['timestamp'].dt.strftime(date_format='%Y-%m-%d, %H:%M:%S')
        pagemoves['diff_link'] = pagemoves['rc_this_oldid'].apply(func=make_diff_link)
        pagemoves['contributions_link'] = pagemoves['username'].apply(func=make_contributions_link)


    try:
        pageremovals = pd.read_csv(
            f'{DATA_DIR}pageremoval/worklist-{project}-pageremoval-full.tsv',
            sep='\t',
            skiprows=1,
            usecols=[ 1, 2, 3, 4, 5, 6, 7, 8 ],
            names=[ 'rc_id', 'rc_timestamp', 'item', 'rc_this_oldid', 'username', 'oresc_damaging', 'oresc_goodfaith', 'editsummary_magic_action' ],
            dtype={ 'rc_id' : int, 'rc_timestamp' : int, 'item' : str, 'rc_this_oldid' : int, 'username' : str, 'oresc_damaging' : float, 'oresc_goodfaith' : float, 'editsummary_magic_action' : str }
        )
    except FileNotFoundError:
        pageremovals = None
    else:
        pageremovals['timestamp'] = pd.to_datetime(pageremovals['rc_timestamp'], format='%Y%m%d%H%M%S')
        pageremovals['item_link'] = pageremovals['item'].apply(func=make_item_link)
        pageremovals['timestamp_formatted'] = pageremovals['timestamp'].dt.strftime(date_format='%Y-%m-%d, %H:%M:%S')
        pageremovals['diff_link'] = pageremovals['rc_this_oldid'].apply(func=make_diff_link)
        pageremovals['contributions_link'] = pageremovals['username'].apply(func=make_contributions_link)

    return render_template(
        'by_project.html',
        title='Unpatrolled changes by project',
        project=project,
        projects=projects,
        sitelinks=sitelink_df,
        pagemoves=pagemoves,
        pageremovals=pageremovals
    )


@app.route('/by_lang', methods=['GET', 'POST'])
@app.route('/by_lang/<string:language>')
def by_lang(language='de'):  #  -> Union[str, .wrappers.Response]
    if request.method == 'POST':
        return redirect(f'/by_lang/{request.form.get("lang")}')

    language_lst = []
    for term_file in glob(f'{DATA_DIR}term/worklist-*-terms-full.tsv'):
        match = fullmatch(fr'^{DATA_DIR}term/worklist-(.*)-terms-full.tsv$', term_file)
        if match is not None:
            language_lst.append(match.group(1))
    for termee_file in glob(f'{DATA_DIR}termee/worklist-*-terms-in-editentity-full.tsv'):
        match = fullmatch(fr'^{DATA_DIR}termee/worklist-(.*)-terms-in-editentity-full.tsv$', termee_file)
        if match is not None:
            language_lst.append(match.group(1))
    for termeec_file in glob(f'{DATA_DIR}termeec/worklist-*-terms-in-editentity-create-full.tsv'):
        match = fullmatch(fr'^{DATA_DIR}termeec/worklist-(.*)-terms-in-editentity-create-full.tsv$', termeec_file)
        if match is not None:
            language_lst.append(match.group(1))
    language_lst = sorted(list(set(language_lst)))


    try:
        terms = pd.read_csv(
            f'{DATA_DIR}term/worklist-{language}-terms-full.tsv',
            sep='\t',
            skiprows=1,
            usecols=[ 1, 2, 3, 4, 5, 6, 7, 8 ],
            names=[ 'rc_id', 'rc_timestamp', 'item', 'rc_this_oldid', 'username', 'oresc_damaging', 'oresc_goodfaith', 'editsummary_magic_action' ],
            dtype={ 'rc_id' : int, 'rc_timestamp' : int, 'item' : str, 'rc_this_oldid' : int, 'username' : str, 'oresc_damaging' : float, 'oresc_goodfaith' : float, 'editsummary_magic_action' : str }
        )
    except FileNotFoundError:
        terms = None
    else:
        terms['timestamp'] = pd.to_datetime(terms['rc_timestamp'], format='%Y%m%d%H%M%S')
        terms['item_link'] = terms['item'].apply(func=make_item_link)
        terms['timestamp_formatted'] = terms['timestamp'].dt.strftime(date_format='%Y-%m-%d, %H:%M:%S')
        terms['diff_link'] = terms['rc_this_oldid'].apply(func=make_diff_link)
        terms['contributions_link'] = terms['username'].apply(func=make_contributions_link)


    try:
        termsee = pd.read_csv(
            f'{DATA_DIR}termee/worklist-{language}-terms-in-editentity-full.tsv',
            sep='\t',
            skiprows=1,
            usecols=[ 1, 2, 3, 4, 5, 6, 7, 8 ],
            names=[ 'rc_id', 'rc_timestamp', 'item', 'rc_this_oldid', 'username', 'oresc_damaging', 'oresc_goodfaith', 'editsummary_magic_action' ],
            dtype={ 'rc_id' : int, 'rc_timestamp' : int, 'item' : str, 'rc_this_oldid' : int, 'username' : str, 'oresc_damaging' : float, 'oresc_goodfaith' : float, 'editsummary_magic_action' : str }
        )
    except FileNotFoundError:
        termsee = None
    else:
        termsee['timestamp'] = pd.to_datetime(termsee['rc_timestamp'], format='%Y%m%d%H%M%S')
        termsee['item_link'] = termsee['item'].apply(func=make_item_link)
        termsee['timestamp_formatted'] = termsee['timestamp'].dt.strftime(date_format='%Y-%m-%d, %H:%M:%S')
        termsee['diff_link'] = termsee['rc_this_oldid'].apply(func=make_diff_link)
        termsee['contributions_link'] = termsee['username'].apply(func=make_contributions_link)

    try:
        termseec = pd.read_csv(
            f'{DATA_DIR}termeec/worklist-{language}-terms-in-editentity-create-full.tsv',
            sep='\t',
            skiprows=1,
            usecols=[ 1, 2, 3, 4, 5, 6, 7, 8 ],
            names=[ 'rc_id', 'rc_timestamp', 'item', 'rc_this_oldid', 'username', 'oresc_damaging', 'oresc_goodfaith', 'editsummary_magic_action' ],
            dtype={ 'rc_id' : int, 'rc_timestamp' : int, 'item' : str, 'rc_this_oldid' : int, 'username' : str, 'oresc_damaging' : float, 'oresc_goodfaith' : float, 'editsummary_magic_action' : str }
        )
    except FileNotFoundError:
        termseec = None
    else:
        termseec['timestamp'] = pd.to_datetime(termseec['rc_timestamp'], format='%Y%m%d%H%M%S')
        termseec['item_link'] = termseec['item'].apply(func=make_item_link)
        termseec['timestamp_formatted'] = termseec['timestamp'].dt.strftime(date_format='%Y-%m-%d, %H:%M:%S')
        termseec['diff_link'] = termseec['rc_this_oldid'].apply(func=make_diff_link)
        termseec['contributions_link'] = termseec['username'].apply(func=make_contributions_link)

    return render_template(
        'by_language.html',
        title='Unpatrolled changes by language',
        language=language,
        languages=language_lst,
        terms=terms,
        termsee=termsee,
        termseec=termseec
    )


@app.route('/by_property', methods=['GET', 'POST'])
@app.route('/by_property/<string:prop>')
def by_property(prop='P279'):  #  -> Union[str, .wrappers.Response]
    if request.method == 'POST':
        return redirect(f'/by_property/{request.form.get("prop")}')

    property_lst = []
    for prop_file in glob(f'{DATA_DIR}property/worklist-*-full.tsv'):
        match = fullmatch(fr'^{DATA_DIR}property/worklist-(.*)-full.tsv$', prop_file)
        if match is not None:
            property_lst.append(match.group(1))
    property_lst = sorted(list(set(property_lst)))

    try:
        data = pd.read_csv(
            f'{DATA_DIR}property/worklist-{prop}-full.tsv',
            sep='\t',
            skiprows=1,
            usecols=[ 1, 2, 3, 4, 5, 6, 7, 8 ],
            names=[ 'rc_id', 'rc_timestamp', 'item', 'rc_this_oldid', 'username', 'oresc_damaging', 'oresc_goodfaith', 'editsummary_magic_action' ],
            dtype={ 'rc_id' : int, 'rc_timestamp' : int, 'item' : str, 'rc_this_oldid' : int, 'username' : str, 'oresc_damaging' : float, 'oresc_goodfaith' : float, 'editsummary_magic_action' : str }
        )
    except FileNotFoundError:
        data = None
    else:
        data['timestamp'] = pd.to_datetime(data['rc_timestamp'], format='%Y%m%d%H%M%S')
        data['item_link'] = data['item'].apply(func=make_item_link)
        data['timestamp_formatted'] = data['timestamp'].dt.strftime(date_format='%Y-%m-%d, %H:%M:%S')
        data['diff_link'] = data['rc_this_oldid'].apply(func=make_diff_link)
        data['contributions_link'] = data['username'].apply(func=make_contributions_link)

    return render_template(
        'by_property.html',
        title='Unpatrolled changes by property',
        prop=prop,
        properties=property_lst,
        data=data
    )


@app.route('/editentity', methods=['GET', 'POST'])
@app.route('/editentity/<string:action>')
def editentity(action='create'):  #  -> Union[str, .wrappers.Response]
    if request.method == 'POST':
        return redirect(f'/editentity/{request.form.get("action")}')

    action_mapping = {
        'create' : 'wbeditentity-create',
        'create_item' : 'wbeditentity-create-item',
        'override' : 'wbeditentity-override',
        'update' : 'wbeditentity-update',
        'update_languages' : 'wbeditentity-update-languages',
        'update_languages_short' : 'wbeditentity-update-languages-short',
        'update_languages_and_other_short' : 'wbeditentity-update-languages-and-other-short'
    }

    actions = []
    for dump_file in glob(f'{DATA_DIR}editentity/worklist-*-full.tsv'):
        match = fullmatch(fr'^{DATA_DIR}editentity/worklist-(.*)-full.tsv$', dump_file)
        if match is None:
            continue
        for key, value in action_mapping.items():
            if value == match.group(1):
                actions.append(key)
    actions = sorted(list(set(actions)))

    try:
        data = pd.read_csv(
            f'{DATA_DIR}editentity/worklist-{action_mapping.get(action)}-full.tsv',
            sep='\t',
            skiprows=1,
            usecols=[ 1, 2, 3, 4, 5, 6, 7, 8 ],
            names=[ 'rc_id', 'rc_timestamp', 'item', 'rc_this_oldid', 'username', 'oresc_damaging', 'oresc_goodfaith', 'editsummary_magic_action' ],
            dtype={ 'rc_id' : int, 'rc_timestamp' : int, 'item' : str, 'rc_this_oldid' : int, 'username' : str, 'oresc_damaging' : float, 'oresc_goodfaith' : float, 'editsummary_magic_action' : str }
        )
    except FileNotFoundError:
        data = None
    else:
        data['timestamp'] = pd.to_datetime(data['rc_timestamp'], format='%Y%m%d%H%M%S')
        data['item_link'] = data['item'].apply(func=make_item_link)
        data['timestamp_formatted'] = data['timestamp'].dt.strftime(date_format='%Y-%m-%d, %H:%M:%S')
        data['diff_link'] = data['rc_this_oldid'].apply(func=make_diff_link)
        data['contributions_link'] = data['username'].apply(func=make_contributions_link)

    return render_template(
        'editentity.html',
        title='Complex edits by action',
        action=action,
        actions=actions,
        data=data
    )


@app.route('/progress_by_lang', methods=['GET', 'POST'])
@app.route('/progress_by_lang/<string:lang>')
def progress_by_lang(lang='de'):  #  -> Union[str, .wrappers.Response]
    if request.method == 'POST':
        return redirect(f'/progress_by_lang/{request.form.get("lang")}')

    language_lst = []
    for dump_file in glob(f'{DATA_DIR}progress_by_lang/unpatrolled-*.tsv'):
        match = fullmatch(fr'^{DATA_DIR}progress_by_lang/unpatrolled-(.*).tsv$', dump_file)
        if match is not None:
            language_lst.append(match.group(1))
    language_lst = sorted(list(set(language_lst)))

    try:
        with open(f'{DATA_DIR}progress_by_lang/unpatrolled-{lang}.tsv', mode='r', encoding='utf8') as file_handle:
            unpatrolled = int(file_handle.read().strip())
    except FileNotFoundError:
        unpatrolled = None

    try:
        describe = pd.read_csv(
            f'{DATA_DIR}progress_by_lang/describe-{lang}.tsv',
            sep='\s+',  # pylint: disable=anomalous-backslash-in-string
            names=[ 'parameter', 'value' ],
            dtype={ 'parameter' : str, 'value' : float }
        )
    except FileNotFoundError:
        describe = None
    else:
        describe['value_formatted'] = describe['value'].apply(func=fmt_patrol_delay)

    try:
        with open(f'{DATA_DIR}progress_by_lang/percentiles-{lang}.tsv', mode='r', encoding='utf8') as file_handle:
            percentiles = file_handle.read().strip()
    except FileNotFoundError:
        percentiles = None

    try:
        top_patrollers = pd.read_csv(
            f'{DATA_DIR}progress_patrollers_by_lang/patrollers-{lang}-full.tsv',
            sep='\t',
            skiprows=1,
            names=[ 'username', 'actions' ],
            dtype={ 'username' : str, 'actions' : int }
        )
    except FileNotFoundError:
        top_patrollers = None
    else:
        top_patrollers['patrol_log_link'] = top_patrollers['username'].apply(func=make_patrol_log_link)

    has_plot = isfile(f'{PLOT_DIR}progress_by_lang/patrol-progress_{lang}.png')
    has_percentiles = isfile(f'{PLOT_DIR}progress_by_lang/patrol-progress-percentiles_{lang}.png')

    return render_template(
        'progress_by_lang.html',
        title='Patrol progress statistics by language',
        unpatrolled=unpatrolled,
        describe=describe,
        percentiles=percentiles,
        top_patrollers=top_patrollers,
        language=lang,
        languages=language_lst,
        has_plot=has_plot,
        has_percentiles=has_percentiles
    )


@app.route('/not_ns0', methods=['GET', 'POST'])
@app.route('/not_ns0/<string:namespace>')
def not_ns0(namespace='Wikidata'):  #  -> Union[str, .wrappers.Response]
    if request.method == 'POST':
        return redirect(f'/not_ns0/{request.form.get("namespace")}')

    namespaces = []
    for dump_file in glob(f'{DATA_DIR}not_ns0/worklist-*-full.tsv'):
        match = fullmatch(fr'^{DATA_DIR}not_ns0/worklist-(.*)-full.tsv$', dump_file)
        if match is not None:
            namespaces.append(match.group(1))
    namespaces = sorted(list(set(namespaces)))

    ns_spotter = {}
    for nspace in namespaces:
        ns_spotter[nspace.lower()] = nspace

    try:
        data = pd.read_csv(
            f'{DATA_DIR}not_ns0/worklist-{ns_spotter.get(namespace.lower().replace(" ", "_"))}-full.tsv',
            sep='\t',
            skiprows=1,
            usecols=[ 1, 2, 3, 4, 5, 6, 7 ],
            names=[ 'rc_id', 'rc_timestamp', 'page_title', 'rc_this_oldid', 'username', 'namespace', 'rc_source' ],
            dtype={ 'rc_id' : int, 'rc_timestamp' : int, 'page_title' : str, 'rc_this_oldid' : int, 'username' : str, 'namespace' : str, 'rc_source' : str }
        )
    except FileNotFoundError:
        data = None
    else:
        if data.shape[0] > 0:
            data['diff_link'] = data['rc_this_oldid'].apply(func=make_diff_link)
            data['contributions_link'] = data['username'].apply(func=make_contributions_link)
            data['timestamp'] = pd.to_datetime(data['rc_timestamp'], format='%Y%m%d%H%M%S')
            data['timestamp_formatted'] = data['timestamp'].dt.strftime(date_format='%Y-%m-%d, %H:%M:%S')
            data['full_page_title'] = data.apply(lambda x : fmt_full_page_title(x.page_title, x.namespace), axis=1)
            data['full_page_url'] = data.apply(lambda x : fmt_full_page_url(x.page_title, x.namespace), axis=1)
            data['action'] = data['rc_source'].apply(func=fmt_source)
            data.sort_values(by='timestamp', ascending=False, inplace=True)
        else:
            data = None
            if namespace.lower().replace(' ', '_') == 'user_talk':
                namespaces.remove('User_talk')

    return render_template(
        'not_ns0.html',
        title='Unpatrolled changes outside main namespace',
        data=data,
        namespace=namespace,
        namespaces=namespaces
    )
