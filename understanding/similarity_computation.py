import argparse
import logging
import os

import pandas as pd
import torch
from sklearn.metrics.pairwise import cosine_similarity
from transformers import BertModel, BertTokenizer

from understanding.constant import DATASETS_FOLDER
from understanding.utils import load_dataset, register_logger

# setup library logging
logger = logging.getLogger(__name__)
register_logger(logger)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Initialize BERT model and tokenizer
MODEL_NAME = "bert-base-uncased"
tokenizer = BertTokenizer.from_pretrained(MODEL_NAME)
model = BertModel.from_pretrained(MODEL_NAME).to(device)
model.eval()  # Set model to evaluation mode


def compute_embeddings(sentences):
    """
    Compute BERT embeddings for a list of sentences.

    Args:
        sentences (List[str]): List of sentences to encode.

    Returns:
        torch.Tensor: Tensor of embeddings.
    """
    # Tokenize and encode sentences to get input IDs and attention masks
    inputs = tokenizer(sentences, return_tensors="pt", padding=True, truncation=True)
    with torch.no_grad():
        outputs = model(**inputs)
        embeddings = outputs.last_hidden_state[:, 0, :]  # Use CLS token embeddings
    return embeddings


def compute_max_similarities(embeddings, ground_truth_indices):
    """
    Compute the highest cosine similarity score for each non-ground-truth embedding
    against the embeddings in the ground truth list.

    Args:
        embeddings (torch.Tensor): Tensor of shape (num_sentences, embedding_dim).
        ground_truth_indices (List[int]): Indices of embeddings that belong to the ground truth.

    Returns:
        List[float]: List of highest similarity scores for each non-ground-truth embedding.
    """
    # Compute cosine similarity between all embeddings
    sim_matrix = cosine_similarity(embeddings)

    max_similarities = []
    for i in range(len(sim_matrix)):
        if i in ground_truth_indices:
            # Skip ground truth sentences, no need to compute max similarity for them
            max_similarities.append(None)
        else:
            # Only consider similarities with ground truth indices
            sim_to_ground_truth = sim_matrix[i, ground_truth_indices]
            max_sim = sim_to_ground_truth.max()
            max_similarities.append(max_sim)

    return max_similarities


def process_dataframe(df, user_name):
    """
    Process the DataFrame to compute max similarity scores for each non-ground-truth sentence.

    Args:
        df (pd.DataFrame): Input DataFrame with columns containing sentence lists and ground truth indices.
        user (str): which user and its columns to be used

    Returns:
        pd.DataFrame: DataFrame with an added column for max similarity scores.
    """
    candidates_column = f"{user_name}_personas_candidates"
    ground_truth_column = f"{user_name}_gt_index_list"
    similarity_column = f"{user_name}_candidates_similarities"
    max_sim_scores = []

    for _, row in df.iterrows():
        sentences = row[candidates_column]
        ground_truth_indices = row[ground_truth_column]

        # Compute embeddings for each sentence in the cell
        embeddings = compute_embeddings(sentences)

        # Compute max similarity scores for each non-ground-truth sentence
        max_similarities = compute_max_similarities(embeddings, ground_truth_indices)

        # Store results
        max_sim_scores.append(max_similarities)

    # Add the new column to the DataFrame
    df[similarity_column] = max_sim_scores
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    # Add arguments
    parser.add_argument(
        "--results_csv",
        type=str,
        help="Name of output csv file",
        required=False,
        default="personas_candidates.csv",
    )

    # Parse the arguments
    args = parser.parse_args()

    result_csv_path = os.path.join(DATASETS_FOLDER, args.results_csv)
    existing_df = (
        pd.read_csv(result_csv_path) if os.path.exists(result_csv_path) else None
    )

    # Load dataset and set up data for testing
    persona_df = load_dataset()

    for user in ["user1", "user2"]:
        persona_df = process_dataframe(df=persona_df, user_name=user)