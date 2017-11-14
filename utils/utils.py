import torch
import skimage

def getTransform(center, scale, rot, res):
    h = 200 * scale
    t = torch.eye(3)

    # Scaling
    t[1][1] = res / h
    t[2][2] = res / h

    # Translation
    t[1][3] = res * (-center[1] / h + .5)
    t[2][3] = res * (-center[2] / h + .5)

    # Rotation
    if rot != 0:
        rot = -rot
        local r = torch.eye(3)
        local ang = rot * math.pi / 180
        local s = math.sin(ang)
        local c = math.cos(ang)
        r[1][1] = c
        r[1][2] = -s
        r[2][1] = s
        r[2][2] = c
        # Need to make sure rotation is around center
        local t_ = torch.eye(3)
        t_[1][3] = -res/2
        t_[2][3] = -res/2
        local t_inv = torch.eye(3)
        t_inv[1][3] = res/2
        t_inv[2][3] = res/2
        t = t_inv * r * t_ * t

    return t

def transform(pt, center, scale, rot, res, invert):
    local pt_ = torch.ones(3)
    pt_[1],pt_[2] = pt[1]-1,pt[2]-1

    local t = getTransform(center, scale, rot, res)
    if invert:
        t = torch.inverse(t)
    new_point = (t*pt_):sub(1,2):add(1e-4)

    return new_point:int():add(1)

def crop(img, center, scale, rot, res):
    ul = transform({1,1}, center, scale, 0, res, true)
    br = transform({res+1,res+1}, center, scale, 0, res, true)

    local pad = math.floor(torch.norm((ul - br):float())/2 - (br[1]-ul[1])/2)
    if rot != 0:
        ul = ul - pad
        br = br + pad

    # newDim,newImg,ht,wd

    if img:size():size() > 2:
        newDim = torch.IntTensor({img:size(1), br[2] - ul[2], br[1] - ul[1]})
        newImg = torch.zeros(newDim[1],newDim[2],newDim[3])
        ht = img:size(2)
        wd = img:size(3)
    else:
        newDim = torch.IntTensor({br[2] - ul[2], br[1] - ul[1]})
        newImg = torch.zeros(newDim[1],newDim[2])
        ht = img:size(1)
        wd = img:size(2)

    newX = torch.Tensor({math.max(1, -ul[1] + 2), math.min(br[1], wd+1) - ul[1]})
    newY = torch.Tensor({math.max(1, -ul[2] + 2), math.min(br[2], ht+1) - ul[2]})
    oldX = torch.Tensor({math.max(1, ul[1]), math.min(br[1], wd+1) - 1})
    oldY = torch.Tensor({math.max(1, ul[2]), math.min(br[2], ht+1) - 1})

    if newDim:size(1) > 2:
        newImg:sub(1,newDim[1],newY[1],newY[2],newX[1],newX[2]):copy(img:sub(1,newDim[1],oldY[1],oldY[2],oldX[1],oldX[2]))
    else:
        newImg:sub(newY[1],newY[2],newX[1],newX[2]):copy(img:sub(oldY[1],oldY[2],oldX[1],oldX[2]))

    if rot != 0:
        newImg = image.rotate(newImg, rot * math.pi / 180, 'bilinear')
        if newDim:size(1) > 2:
            newImg = newImg:sub(1,newDim[1],pad,newDim[2]-pad,pad,newDim[3]-pad)
        else
            newImg = newImg:sub(pad,newDim[1]-pad,pad,newDim[2]-pad)

    newImg = image.scale(newImg,res,res)
    return newImg

magic_gaussian = image.gaussian(7)

def drawGaussian(img, pt, sigma):
    # Check if the gaussian is in-bounds
    ul = {math.floor(pt[1] - 3 * sigma), math.floor(pt[2] - 3 * sigma)}
    br = {math.floor(pt[1] + 3 * sigma), math.floor(pt[2] + 3 * sigma)}
    # return the image otherwise
    if (ul[1] > img:size(2) or ul[2] > img:size(1) or br[1] < 1 or br[2] < 1):
        return img
    # Generate gaussian
    size = 6 * sigma + 1
    # Avoid the need of generating the gaussian for each sample
    g = magic_gaussian:clone() # image.gaussian(size) -- , 1 / size, 1)

    # Usable gaussian range
    g_x = {math.max(1, -ul[1]), math.min(br[1], img:size(2)) - math.max(1, ul[1]) + math.max(1, -ul[1])}
    g_y = {math.max(1, -ul[2]), math.min(br[2], img:size(1)) - math.max(1, ul[2]) + math.max(1, -ul[2])}
    # Image range
    img_x = {math.max(1, ul[1]), math.min(br[1], img:size(2))}
    img_y = {math.max(1, ul[2]), math.min(br[2], img:size(1))}
    assert(g_x[1] > 0 and g_y[1] > 0)
    img:sub(img_y[1], img_y[2], img_x[1], img_x[2]):add(g:sub(g_y[1], g_y[2], g_x[1], g_x[2]))
    img[img:gt(1)] = 1
    return img

def shuffleLR(x):
    if x:nDimension() == 4:
        dim = 2
    else:
        assert(x:nDimension() == 3)
        dim = 1

    # Keypoints pairs for 300W_LP, 300VW, 300W and LS3D-W datasets
    matchedParts = {
			{1,17},   {2,16},   {3,15},
			{4,14}, {5,13}, {6,12}, {7,11}, {8,10},
			{18,27},{19,26},{20,25},{21,24},{22,23},
			{37,46},{38,45},{39,44},{40,43},
			{42,47},{41,48},
			{32,36},{33,35},
			{51,53},{50,54},{49,55},{62,64},{61,65},{68,66},{60,56},
			{59,57}
    }

    for i in range(len(matchedParts)):
        idx1, idx2 = unpack(matchedParts[i])
        tmp = x:narrow(dim, idx1, 1):clone()
        x:narrow(dim, idx1, 1):copy(x:narrow(dim, idx2, 1))
        x:narrow(dim, idx2, 1):copy(tmp)

    return x

def flip(x):
    local y = torch.FloatTensor(x:size())
    for i = 1, x:size(1):
        skimage.hflip(y[i], x[i]:float())
    return y:typeAs(x)
