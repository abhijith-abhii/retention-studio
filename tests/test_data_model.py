import json
import numpy as np
import pandas as pd
import pytest
from retention.paths import ROOT
from retention.data import validate, load_csv, feature_frame, FEATURES, FORBIDDEN, ValidationError
from retention.model import load_model

def test_source_quality():
    df,issues=load_csv(ROOT/"data/raw/telco.csv")
    assert len(df)==7043 and df.customerID.is_unique
    assert df.Churn.eq('Yes').sum()==1869
    assert df.TotalCharges.isna().sum()==11
    assert df.loc[df.TotalCharges.isna(),'tenure'].eq(0).all()

@pytest.mark.parametrize('mutation',[
    lambda d:d.assign(customerID='DUPLICATE'),
    lambda d:d.assign(MonthlyCharges=-1),
    lambda d:d.assign(tenure=1.5),
    lambda d:d.assign(Contract='Unknown contract'),
    lambda d:d.assign(Churn='No'),
    lambda d:d.assign(Active='Unknown'),
    lambda d:d.assign(MonthlyCharges='infinity'),
    lambda d:d.assign(customerID=''),
    lambda d:d.assign(tenure=0,TotalCharges=1),
    lambda d:d.assign(InternetService='No',TechSupport='Yes'),
    lambda d:d.drop(columns=['tenure']),
])
def test_invalid_inputs_rejected(scoring,mutation):
    with pytest.raises(ValidationError):validate(mutation(scoring.head(3)),scoring=True)

def test_empty_and_bad_csv_rejected(tmp_path,scoring):
    with pytest.raises(ValidationError):validate(scoring.iloc[:0],scoring=True)
    f=tmp_path/'empty.csv';f.write_text('')
    with pytest.raises(ValidationError):load_csv(f,scoring=True)

def test_missing_predictor_is_explicit(scoring):
    scoring.loc[0,'TotalCharges']=np.nan
    df,issues=validate(scoring,scoring=True)
    assert any('TotalCharges' in x['message'] for x in issues)
    model,_=load_model()
    assert np.isfinite(model.predict_proba(feature_frame(df))).all()

def test_feature_allowlist_and_scoring_consistency(scoring):
    model,_=load_model()
    assert not set(FEATURES)&FORBIDDEN
    before=model.predict_proba(feature_frame(scoring.head(20)))[:,1]
    changed=scoring.head(20).copy();changed['Churn']='Yes';changed['customerID']='999-OTHER';changed['Active']='No'
    after=model.predict_proba(feature_frame(changed))[:,1]
    np.testing.assert_array_equal(before,after)
    reloaded,_=load_model()
    np.testing.assert_array_equal(before,reloaded.predict_proba(feature_frame(scoring.head(20)))[:,1])

def test_disjoint_splits_and_unseen_scoring_pool(scoring):
    split=json.loads((ROOT/'data/training/split_manifest.json').read_text())
    train,val,holdout=(set(split[k]) for k in ['train','validation','holdout'])
    assert not(train&val or train&holdout or val&holdout)
    assert len(train|val|holdout)==7043
    assert set(scoring.customerID)<=holdout
    assert not set(scoring.customerID)&train

def test_saved_holdout_metrics_recompute():
    from retention.model import metrics
    model,meta=load_model()
    df,_=load_csv(ROOT/'data/training/holdout.csv')
    y=df.Churn.eq('Yes').astype(int)
    result=metrics(y,model.predict_proba(feature_frame(df))[:,1],meta['holdout']['threshold'],meta['capacity_fraction'])
    for k in ['precision','recall','f1','roc_auc','pr_auc','brier','precision_at_k','lift_at_k']:
        assert result[k]==pytest.approx(meta['holdout'][k])
