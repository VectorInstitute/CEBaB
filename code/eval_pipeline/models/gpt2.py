from math import ceil

import numpy as np
import torch
from sklearn.metrics import classification_report
from transformers import (
    AutoTokenizer,
)

from eval_pipeline.customized_models.gpt2 import GPT2ForNonlinearSequenceClassification
from eval_pipeline.models.abstract_model import Model


class GPT2ForCEBaB(Model):
    def __init__(self, model_path, device='cpu', batch_size=32):
        self.device = device
        self.model_path = model_path
        self.tokenizer_path = model_path
        self.batch_size = batch_size

        if 'CEBaB/' in self.model_path:
            self.tokenizer_path = self.model_path.split('/')[1].split('.')[0]

        self.model = GPT2ForNonlinearSequenceClassification.from_pretrained(self.model_path)
        self.tokenizer = AutoTokenizer.from_pretrained(self.tokenizer_path)
        # GPT2 was trained without pad token but this is needed to batchify the data.
        # Because of the attention mask, the choice of pad_token will have no effect.
        self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model.to(device)

    def __str__(self):
        return self.model_path.split('/')[-1]

    def preprocess(self, df):
        x = self.tokenizer(df['description'].to_list(), padding=True, truncation=True, return_tensors='pt')
        y = df['review_majority'].astype(int)

        return x, y

    def fit(self, dataset):
        # assume model was already trained
        pass

    def predict_proba(self, dataset):
        self.model.eval()

        x, y = self.preprocess(dataset)

        # get the predictions batch per batch
        probas = []
        for i in range(ceil(len(dataset) / self.batch_size)):
            x_batch = {k: v[i * self.batch_size:(i + 1) * self.batch_size].to(self.device) for k, v in x.items()}
            probas.append(torch.nn.functional.softmax(self.model(**x_batch).logits.cpu(), dim=-1).detach())

        probas = torch.concat(probas)
        probas = np.round(probas.numpy(), decimals=4)

        predictions = np.argmax(probas, axis=1)
        clf_report = classification_report(y.to_numpy(), predictions, output_dict=True)

        return probas, clf_report

    def get_embeddings(self, sentences_list):
        x = self.tokenizer(sentences_list, padding=True, truncation=True, return_tensors='pt')
        embeddings = []
        for i in range(ceil(len(x['input_ids']) / self.batch_size)):
            x_batch = {k: v[i * self.batch_size:(i + 1) * self.batch_size].to(self.device) for k, v in x.items()}
            embeddings.append(self.model.transformer(**x_batch).last_hidden_state[:, 0, :].detach().cpu().tolist())

        return embeddings

    def get_classification_head(self):
        return self.model.score
