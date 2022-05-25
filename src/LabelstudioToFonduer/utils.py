from fonduer.candidates import MentionNgrams

def resolve_relations(relations, id_label):
    resolved = []
    for relation in relations:
        resolved.append((id_label.get(relation[0]), id_label.get(relation[1])))
    return set(resolved)


def determine_ngram_size(export, label):
    lengths = []
    for doc in export:
        for spot in doc["spots"]:
            if spot["label"] == label:
                lengths.append(len(spot.get("text").split(" ")))
    return MentionNgrams(n_max=max(lengths), n_min=min(lengths))