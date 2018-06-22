wget http://lcl.uniroma1.it/wsdeval/data/WSD_Unified_Evaluation_Datasets.zip
unzip WSD_Unified_Evaluation_Datasets.zip
rm WSD_Unified_Evaluation_Datasets.zip
mv WSD_Unified_Evaluation_Datasets/Scorer.java .
rm -r WSD_Unified_Evaluation_Datasets
javac Scorer.java
