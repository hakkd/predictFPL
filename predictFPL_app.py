import pandas as pd
import re
import random
import requests
import pickle
from tqdm.auto import tqdm
import panel as pn

# set url for fantasy PL API
api_url = "https://fantasy.premierleague.com/api/bootstrap-static/"

# download the webpage
data = requests.get(api_url)

json = data.json()

json.keys()

# build a dataframe
players = pd.DataFrame(json['elements'])

# use all columns 
players_df_select = players

# combine first and last names to get player full names
players_df_select['full_name'] = players_df_select[['first_name', 'second_name']].agg(' '.join, axis=1)

# drop first and last name columns
players_df_select = players_df_select.drop(['first_name', 'second_name'], axis = 1)

# player prices are 10x the true value. Divide the prices by 10 to get the true values
players_df_select['now_cost'] = players_df_select['now_cost']/10

# get team info
teams = pd.DataFrame(json['teams'])

# get team defensive strength
team_strength_def = teams[['id', 'name', 'strength_defence_away', 'strength_defence_home']]

# get team attack strength
team_strength_att = teams[['id', 'name', 'strength_attack_away', 'strength_attack_home']]

# get position information from 'element_types'
positions = pd.DataFrame(json['element_types'])

# merge player data with teams and positions
player_team_merge = pd.merge(
    left = players_df_select,
    right = teams,
    left_on = 'team',
    right_on = 'id'
)

# merge players with positions
player_team_pos_merge = pd.merge(
    left = player_team_merge,
    right = positions,
    left_on = 'element_type',
    right_on = 'id'
)

# rename columns
player_team_pos_merge = player_team_pos_merge.rename(
    columns={'name':'team_name', 'singular_name_short':'position_name'}
)

# function for getting specific player gameweek history
def get_history(player_id):
    ''' get all gameweek history for a given player'''
    
    # request data from API 
    data = requests.get("https://fantasy.premierleague.com/api/element-summary/" + str(player_id) + "/")
    json = data.json()
    
    # turn data into Pandas dataframe
    df = pd.DataFrame(json['history'])
    
    return df

tqdm.pandas()

# join team name
players = players.merge(
    teams[['id', 'name']],
    left_on='team',
    right_on='id',
    suffixes=['_player', None]
).drop(['team', 'id'], axis=1)

# join player positions
players = players.merge(
    positions[['id', 'singular_name_short']],
    left_on='element_type',
    right_on='id'
).drop(['element_type', 'id'], axis=1)

# rename columns
players = players.rename(
    columns={'name':'team', 'singular_name_short':'position'}
)

# get gameweek history for all players
points = players['id_player'].progress_apply(get_history)

# combine results into one dataframe
points = pd.concat(df for df in points)

# join full_name
points = players[['id_player', 'full_name', 'team', 'position']].merge(
    points,
    left_on='id_player',
    right_on='element'
)

# merge opponent defensive strength
points = pd.merge(left = points,
                  right = team_strength_def[['id', 'strength_defence_away', 
                                             'strength_defence_home']],
                  how = 'left',
                  left_on = 'opponent_team',
                  right_on = 'id'
).drop(
    'id', axis = 1
).rename(
    columns={'strength_defence_away':'opp_def_strength_away', 'strength_defence_home':'opp_def_strength_home'}
)

# assign correct home/away opponent defensive strength for each fixture
def opp_def_strength(row):
    if row['was_home'] == False:
        return row['opp_def_strength_home']
    elif row['was_home'] == True:
        return row['opp_def_strength_away']
    else:
        return "Unknown"

points['opp_def_strength'] = points.apply(lambda row: opp_def_strength(row), axis = 1)

points = points.drop(['opp_def_strength_home','opp_def_strength_away'], axis = 1)

# merge opponent attack strength
points = pd.merge(left = points,
                  right = team_strength_att[['id', 'strength_attack_away', 
                                             'strength_attack_home']],
                  how = 'left',
                  left_on = 'opponent_team',
                  right_on = 'id'
).drop(
    'id', axis = 1
).rename(
    columns={'strength_attack_away':'opp_att_strength_away', 
             'strength_attack_home':'opp_att_strength_home'}
)

# assign correct home/away opponent attack strength for each fixture
def opp_att_strength(row):
    if row['was_home'] == False:
        return row['opp_att_strength_home']
    elif row['was_home'] == True:
        return row['opp_att_strength_away']
    else:
        return "Unknown"

points['opp_att_strength'] = points.apply(lambda row: opp_att_strength(row), axis = 1)

points = points.drop(['opp_att_strength_home','opp_att_strength_away'], axis = 1)

# get 20 top scoring players in all positions
gks = points.loc[points['position'] == 'GKP']
defs = points.loc[points['position'] == 'DEF']
mids = points.loc[points['position'] == 'MID']
fwds = points.loc[points['position'] == 'FWD']

top_20_gks = gks.groupby(
    ['element', 'full_name']
).agg(
    {'total_points':'sum'}
).reset_index(
).sort_values(
    'total_points', ascending=False
).head(20)

top_20_defs = defs.groupby(
    ['element', 'full_name']
).agg(
    {'total_points':'sum'}
).reset_index(
).sort_values(
    'total_points', ascending=False
).head(20)

top_20_mids = mids.groupby(
    ['element', 'full_name']
).agg(
    {'total_points':'sum'}
).reset_index(
).sort_values(
    'total_points', ascending=False
).head(20)

top_20_fwds = fwds.groupby(
    ['element', 'full_name']
).agg(
    {'total_points':'sum'}
).reset_index(
).sort_values(
    'total_points', ascending=False
).head(20)

#combine top 20 scorers
top_20_all_pos = pd.concat([top_20_gks, top_20_defs, top_20_mids, top_20_fwds], axis = 0)

# select columns of interest
points_select = points[['id_player', 'full_name', 'team', 'position',
                        'total_points',
                        'minutes', 'goals_scored', 'assists', 'clean_sheets', 
                        'goals_conceded', 'own_goals',
                        'saves', 'bonus', 'bps', 'influence', 'creativity', 'threat', 'ict_index',
                        'expected_goals', 'expected_assists', 'expected_goal_involvements', 
                        'expected_goals_conceded', 'opp_att_strength', 'opp_def_strength']]

points_select['influence'].astype(float)

def last_5_player(df, player_id):
    ''' 
    get the mean stats for a given player_id over the last 5 fixtures
    prior to most recent fixture and the total points from the most 
    recent fixture. 
    
    assume dataframe is sorted from oldest to newest fixtures
    '''
    df = df[df['id_player'] == player_id]
    
    last_5 = df.tail(5)
    
    d = {'name': last_5['full_name'].iloc[0],
         'id': last_5['id_player'].iloc[0],
         'team': last_5['team'].iloc[0],
        'position': last_5['position'].iloc[0],
        'mean_points': last_5['total_points'].mean(),
        'mean_minutes': last_5['minutes'].mean(),
        'mean_goals_scored': last_5['goals_scored'].mean(),
        'mean_assists': last_5['assists'].mean(),
        'mean_clean_sheets': last_5['clean_sheets'].mean(),
        'mean_goals_conceded': last_5['goals_conceded'].mean(),
        'mean_own_goals': last_5['own_goals'].mean(),
        'mean_saves': last_5['saves'].mean(),
        'mean_bonus': last_5['bonus'].mean(),
        'mean_bps': last_5['bps'].mean(),
        'mean_influence': last_5['influence'].astype(float).mean(),
        'mean_creativity': last_5['creativity'].astype(float).mean(),
        'mean_threat': last_5['threat'].astype(float).mean(),
        'mean_ict': last_5['ict_index'].astype(float).mean(),
        'mean_xg': last_5['expected_goals'].astype(float).mean(),
        'mean_xa': last_5['expected_assists'].astype(float).mean(),
        'mean_xgi': last_5['expected_goal_involvements'].astype(float).mean(),
        'mean_xgc': last_5['expected_goals_conceded'].astype(float).mean(),
        'mean_opp_att': last_5['opp_att_strength'].mean(),
        'mean_opp_def': last_5['opp_def_strength'].mean()}
    
    last_5_mean = pd.DataFrame(data = d, index = [0])
    
    return last_5_mean

def last_5_all(df):
    ''' get last mean stats for all players in df over the last 5 fixtures
    prior to most recent fixture and the total points from the most 
    recent fixture.
    '''
    last_5_all = pd.DataFrame() # empty dataframe
    for p in df['id_player'].unique():
        player_df = last_5_player(df, p)
        last_5_all = pd.concat([last_5_all, player_df])
    return last_5_all

# apply function
last_5_df = last_5_all(points_select)

# load pickled model
with open('mid_model_20230112.pkl', 'rb') as file:  
    mid_model = pickle.load(file)
    
# apply the model
def predict_points(player_data, test_data, model) -> None:
    '''
    apply predictive model to the data
    '''
    prediction = player_data.assign(predicted=model.predict(test_data))
    
    return prediction[['name', 'team', 'position', 
                       'predicted']].sort_values('predicted', ascending=False).head(10).reset_index()

mid_data = last_5_df[last_5_df['position'] == 'MID']

mid_test = mid_data[['mean_ict', 'mean_xgi']]

# apply prediction model
predicted = predict_points(mid_data, mid_test, mid_model)

# create panel dashboard
pn.extension(sizing_mode="stretch_width")

pn.template.FastListTemplate(
    site="PredictFPL", 
    title="Next Gameweek Player Points Prediction", 
    sidebar=[], 
    main=[predicted,
         top_20_all_pos.sort_values('total_points', ascending=False)[['full_name', 'total_points']].head(10)],
    main_max_width="650px"
).servable();