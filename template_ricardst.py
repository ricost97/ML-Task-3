# This serves as a template which will guide you through the implementation of this task.  It is advised
# to first read the whole template and get a sense of the overall structure of the code before trying to fill in any of the TODO gaps
# First, we import necessary libraries:
import numpy as np
from torchvision import transforms
from torch.utils.data import DataLoader, TensorDataset
import os
import torch
import torchvision.models as models
from torchvision import transforms
import torchvision.datasets as datasets
import torch.nn as nn
import torch.nn.functional as F
from sklearn.preprocessing import normalize

# The device is automatically set to GPU if available, otherwise CPU
# If you want to force the device to CPU, you can change the line to
# device = torch.device("cpu")
# When using the GPU, it is important that your model and all data are on the 
# same device.
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

def generate_embeddings():
    """
    Transform, resize and normalize the images and then use a pretrained model to extract 
    the embeddings.
    """
    # TODO: define a transform to pre-process the images
    # The required pre-processing depends on the pre-trained model you choose 
    # below. 
    # See https://pytorch.org/vision/stable/models.html#using-the-pre-trained-models
    # Define transformations for the input required by ResNet-50
    train_transforms = transforms.Compose([
        transforms.Resize(256),            # Resize the image to 256x256 pixels
        transforms.CenterCrop(224),        # Crop the image to 224x224 pixels
        transforms.ToTensor(),             # Convert the image to a tensor
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    train_dataset = datasets.ImageFolder(root="dataset/", transform=train_transforms)
    # Hint: adjust batch_size and num_workers to your PC configuration, so that you don't 
    # run out of memory (VRAM if on GPU, RAM if on CPU)
    train_loader = DataLoader(dataset=train_dataset,
                              batch_size=4,
                              shuffle=False,
                              pin_memory=True, num_workers=4)

    # TODO: define a model for extraction of the embeddings (Hint: load a pretrained model,
    #  more info here: https://pytorch.org/vision/stable/models.html)
    model = models.resnet50(weights='IMAGENET1K_V2')

    model.to(device)
    embedding_size = 2048 # Dummy variable, replace with the actual embedding size once you 
    # pick your model
    num_images = len(train_dataset)
    embeddings = np.zeros((num_images, embedding_size))
    # TODO: Use the model to extract the embeddings. Hint: remove the last layers of the 
    # model to access the embeddings the model generates. 

    # Remove the last fully connected layer to use the model as a fixed feature extractor
    class FeatureExtractor(nn.Module):
        def __init__(self, model):
            super(FeatureExtractor, self).__init__()
            # Everything except the final layer
            self.features = nn.Sequential(*list(model.children())[:-1])

        def forward(self, x):
            x = self.features(x)
            # Flatten the output for each image
            x = torch.flatten(x, 1)
            return x

    # Instantiate the feature extractor
    feature_extractor = FeatureExtractor(model)
    feature_extractor.to(device)
    feature_extractor.eval()  # Set the model to evaluation mode

    with torch.no_grad():  # No need to compute gradients (for faster processing)
        start = 0
        for images, _ in train_loader:
            images = images.to(device)
            outputs = feature_extractor(images)
            batch_size = images.size(0)
            embeddings[start:start + batch_size] = outputs.cpu().numpy()
            start += batch_size
    print("Saving embeddings...")
    np.save('dataset/embeddings.npy', embeddings)


def get_data(file, train=True):
    """
    Load the triplets from the file and generate the features and labels.

    input: file: string, the path to the file containing the triplets
          train: boolean, whether the data is for training or testing

    output: X: numpy array, the features
            y: numpy array, the labels
    """
    triplets = []
    with open(file) as f:
        for line in f:
            triplets.append(line)

    # generate training data from triplets
    train_dataset = datasets.ImageFolder(root="dataset/",
                                         transform=None)
    filenames = [s[0].split('/')[-1].replace('.jpg', '') for s in train_dataset.samples]
    embeddings = np.load('dataset/embeddings.npy')
    # TODO: Normalize the embeddings
    
    embeddings = normalize(embeddings, norm='l2')

    file_to_embedding = {}
    for i in range(len(filenames)):
        file_to_embedding[filenames[i]] = embeddings[i]
    X = []
    y = []
    # use the individual embeddings to generate the features and labels for triplets
    for t in triplets:
        emb = [file_to_embedding['food\\' + a] for a in t.split()]
        X.append(np.hstack([emb[0], emb[1], emb[2]]))
        y.append(1)
        # Generating negative samples (data augmentation)
        if train:
            X.append(np.hstack([emb[0], emb[2], emb[1]]))
            y.append(0)
    X = np.vstack(X)
    y = np.hstack(y)
    print("Loaded data...")
    return X, y

# Hint: adjust batch_size and num_workers to your PC configuration, so that you 
# don't run out of memory (VRAM if on GPU, RAM if on CPU)
def create_loader_from_np(X, y = None, train = True, batch_size=64, shuffle=True, num_workers = 4):
    """
    Create a torch.utils.data.DataLoader object from numpy arrays containing the data.

    input: X: numpy array, the features
           y: numpy array, the labels
    
    output: loader: torch.data.util.DataLoader, the object containing the data
    """
    if train:
        # Attention: If you get type errors you can modify the type of the
        # labels here
        dataset = TensorDataset(torch.from_numpy(X).type(torch.float), 
                                torch.from_numpy(y).type(torch.long))
    else:
        dataset = TensorDataset(torch.from_numpy(X).type(torch.float))
    loader = DataLoader(dataset=dataset,
                        batch_size=batch_size,
                        shuffle=shuffle,
                        pin_memory=True, num_workers=num_workers)
    return loader

# TODO: define a model. Here, the basic structure is defined, but you need to fill in the details
class Net(nn.Module):
    """
    The model class, which defines our classifier.
    """
    def __init__(self):
        """
        The constructor of the model.
        """
        super().__init__()
        self.fc1 = nn.Linear(6144, 1024)  # First layer
        self.fc2 = nn.Linear(1024, 128)   # Second layer
        self.fc3 = nn.Linear(128, 1)      # Output layer

    def forward(self, x):
        """
        The forward pass of the model.

        input: x: torch.Tensor, the input to the model

        output: x: torch.Tensor, the output of the model
        """
        x = F.relu(self.fc1(x))  # Activation function for first layer
        x = F.relu(self.fc2(x))  # Activation function for second layer
        x = torch.sigmoid(self.fc3(x))  # Sigmoid activation function for output layer
        return x

def train_model(train_loader):
    """
    The training procedure of the model; it accepts the training data, defines the model 
    and then trains it.

    input: train_loader: torch.data.util.DataLoader, the object containing the training data
    
    output: model: torch.nn.Module, the trained model
    """
    print("Training model...")
    model = Net()
    model.train()
    model.to(device)
    n_epochs = 10
    # TODO: define a loss function, optimizer and proceed with training. Hint: use the part 
    # of the training data as a validation split. After each epoch, compute the loss on the 
    # validation split and print it out. This enables you to see how your model is performing 
    # on the validation data before submitting the results on the server. After choosing the 
    # best model, train it on the whole training data.
    for epoch in range(n_epochs):        
        for [X, y] in train_loader:
            pass
    print("Saving model...")
    return model

def test_model(model, loader):
    """
    The testing procedure of the model; it accepts the testing data and the trained model and 
    then tests the model on it.

    input: model: torch.nn.Module, the trained model
           loader: torch.data.util.DataLoader, the object containing the testing data
        
    output: None, the function saves the predictions to a results.txt file
    """
    print("Testing model...")
    model.eval()
    predictions = []
    predictions_nr = []
    # Iterate over the test data
    with torch.no_grad(): # We don't need to compute gradients for testing
        for [x_batch] in loader:
            x_batch= x_batch.to(device)
            predicted = model(x_batch)
            predicted = predicted.cpu().numpy()
            predictions_nr.append(predicted)
            # Rounding the predictions to 0 or 1
            predicted[predicted >= 0.5] = 1
            predicted[predicted < 0.5] = 0
            predictions.append(predicted)
        predictions = np.vstack(predictions)
        predictions_nr = np.vstack(predictions_nr)
    print("Saving results...")
    np.savetxt("results.txt", predictions, fmt='%i')
    np.savetxt("results_nr.txt", predictions_nr, fmt='%i')


# Main function. You don't have to change this
if __name__ == '__main__':
    TRAIN_TRIPLETS = 'train_triplets.txt'
    TEST_TRIPLETS = 'test_triplets.txt'

    # generate embedding for each image in the dataset
    if(os.path.exists('dataset/embeddings.npy') == False):
        generate_embeddings()

    # load the training data
    X, y = get_data(TRAIN_TRIPLETS)
    # Create data loaders for the training data
    train_loader = create_loader_from_np(X, y, train = True, batch_size=64)
    # delete the loaded training data to save memory, as the data loader copies
    del X
    del y

    # repeat for testing data
    X_test, y_test = get_data(TEST_TRIPLETS, train=False)
    test_loader = create_loader_from_np(X_test, train = False, batch_size=2048, shuffle=False)
    del X_test
    del y_test

    # define a model and train it
    model = train_model(train_loader)
    
    # test the model on the test data
    test_model(model, test_loader)
    print("Results saved to results.txt")
