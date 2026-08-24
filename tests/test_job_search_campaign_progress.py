from app.services.job_search_campaign_progress import campaign_match,progress

def campaign():return {"id":"c1","status":"active","target_countries":["Canada"],"target_occupations":["Production Supervisor"],"target_employers":[]}
def test_matching_requires_campaign_country_and_occupation():
 result=campaign_match(campaign(),{"country":"Canada","title":"Production Supervisor - PET","company":"A"})
 assert result["matched"] is True
 assert result["safety"]["match_is_not_eligibility"] is True

def test_nonmatching_country_does_not_match_campaign():
 assert campaign_match(campaign(),{"country":"Germany","title":"Production Supervisor"})["matched"] is False

def test_employer_target_is_required_when_campaign_has_employers():
 row={**campaign(),"target_employers":["Husky"]}
 assert campaign_match(row,{"country":"Canada","title":"Production Supervisor","company":"Other"})["matched"] is False

def test_progress_counts_recorded_application_states_only():
 result=progress(campaign(),[{"job_id":"1"},{"job_id":"2"}],[{"state":"interview"},{"state":"offer"},{"state":"rejected"}])
 assert result["vacancies_associated"]==2
 assert result["applications_tracked"]==3
 assert result["interviews"]==1
 assert result["offers_or_hires"]==1
 assert result["safety"]["employer_response_not_inferred"] is True
